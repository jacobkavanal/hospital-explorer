"""Fetch full national releases and atomically publish a validated SQLite snapshot."""

import argparse
from datetime import datetime, timezone
import fcntl
import json
import os
from pathlib import Path
import sqlite3

from catalog import read_catalogs, signature
from ingest import all_pages
from store import compare, initialize, insert_page, row_hashes

ROOT = Path(__file__).parent
DATA = ROOT / "data"


def utcnow():
    return datetime.now(timezone.utc).isoformat()


def write_status(path, status):
    temp = path.with_suffix('.tmp')
    temp.write_text(json.dumps(status, indent=2) + '\n')
    os.replace(temp, path)


def refresh(data_dir=DATA, *, resolver=read_catalogs, pages=all_pages):
    data_dir = Path(data_dir)
    data_dir.mkdir(parents=True, exist_ok=True)
    with (data_dir / 'refresh.lock').open('a') as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise RuntimeError('Another refresh is running')
        started = utcnow()
        attempt = data_dir / 'raw' / datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S.%fZ')
        attempt.mkdir(parents=True)
        current, staging = data_dir / 'hospital.sqlite', attempt / 'snapshot.sqlite'
        old = sqlite3.connect(f'file:{current}?mode=ro', uri=True) if current.exists() else None
        db = None
        status = {'started_at': started, 'state': 'running', 'attempt': str(attempt), 'sources': {}}
        write_status(data_dir / 'status.json', status)
        try:
            contracts = resolver(attempt / 'metadata-before')
            status['year'] = contracts['inpatient']['year']
            db = initialize(staging)
            for source, contract in contracts.items():
                count, evidence = 0, []
                for page in pages(source, contract, attempt / source):
                    insert_page(db, source, page.records)
                    count += len(page.records)
                    evidence.append(str(page.capture_dir.resolve()))
                    print(f'{source}: {count} rows', flush=True)
                if not count:
                    raise ValueError(f'Empty complete source: {source}')
                hashes = row_hashes(db, source)
                previous_meta = old.execute('SELECT year,last_data_change FROM source_versions WHERE source=?', (source,)).fetchone() if old else None
                same_scope = previous_meta is not None and previous_meta[0] == contract['year']
                previous_hashes = row_hashes(old, source) if same_scope else {}
                changes = compare(previous_hashes, hashes)
                changes['baseline'] = not same_scope
                changed = any(changes[k] for k in ['added','removed','changed'])
                last_change = utcnow() if changed or not same_scope else previous_meta[1]
                db.execute('INSERT INTO source_versions VALUES (?,?,?,?,?,?,?,?,?)', (
                    source, contract['dataset_id'], contract['year'], utcnow(), last_change,
                    count, json.dumps(contract['metadata']), json.dumps(evidence), json.dumps(changes)))
                status['sources'][source] = {'rows': count, 'changes': changes}
                write_status(data_dir / 'status.json', status)
            if signature(contracts) != signature(resolver(attempt / 'metadata-after')):
                raise ValueError('Source metadata changed during refresh; retry from a fresh release')
            actual = db.execute('SELECT count(*) FROM hospital_results').fetchone()[0]
            expected = db.execute('SELECT count(*) FROM inpatient').fetchone()[0]
            if actual != expected:
                raise ValueError('Join multiplied or dropped inpatient records')
            status['join_coverage'] = dict(db.execute('SELECT cost_status,count(*) FROM hospital_results GROUP BY cost_status'))
            status['profile_coverage'] = dict(db.execute('SELECT profile_status,count(*) FROM hospital_results GROUP BY profile_status'))
            db.commit()
            if db.execute('PRAGMA integrity_check').fetchone()[0] != 'ok':
                raise ValueError('SQLite integrity check failed')
            db.close()
            db = None
            if old:
                old.close()
                old = None
            # Queries open one read-only connection; existing readers keep the old file.
            with staging.open('rb') as handle:
                os.fsync(handle.fileno())
            os.replace(staging, current)
            status.update(state='success', finished_at=utcnow(), database=str(current))
            write_status(data_dir / 'status.json', status)
            return status
        except Exception as error:
            status.update(state='failed', finished_at=utcnow(), error=str(error))
            write_status(data_dir / 'status.json', status)
            raise
        finally:
            if db:
                db.close()
            if old:
                old.close()
            staging.unlink(missing_ok=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--data-dir', type=Path, default=DATA)
    args = parser.parse_args()
    refresh(args.data_dir)
