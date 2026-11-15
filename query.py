"""Run a read-only, query-time hospital join against the published snapshot."""

import argparse
import json
from pathlib import Path
import sqlite3


def lookup(database, *, ccn=None, drg=None, limit=20):
    if not 1 <= limit <= 1000:
        raise ValueError('limit must be between 1 and 1000')
    db = sqlite3.connect(f'file:{Path(database).resolve()}?mode=ro', uri=True)
    db.row_factory = sqlite3.Row
    try:
        clauses, params = [], []
        for column, value in [('ccn', ccn), ('drg', drg)]:
            if value is not None:
                clauses.append(f'{column} = ?')
                params.append(value)
        sql = 'SELECT * FROM hospital_results'
        if clauses:
            sql += ' WHERE ' + ' AND '.join(clauses)
        sql += ' ORDER BY ccn, drg LIMIT ?'
        return [dict(row) for row in db.execute(sql, params + [limit])]
    finally:
        db.close()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--ccn')
    parser.add_argument('--drg')
    parser.add_argument('--limit', type=int, default=20)
    parser.add_argument('--status', action='store_true', help='Show latest attempt and published-source freshness')
    parser.add_argument('--database', type=Path, default=Path(__file__).parent / 'data' / 'hospital.sqlite')
    args = parser.parse_args()
    if args.status:
        db = sqlite3.connect(f'file:{args.database.resolve()}?mode=ro', uri=True)
        db.row_factory = sqlite3.Row
        try:
            sources = [dict(row) for row in db.execute(
                'SELECT source,dataset_id,year,retrieved_at,last_data_change,row_count,changes_json FROM source_versions')]
        finally:
            db.close()
        status_path = args.database.parent / 'status.json'
        print(json.dumps({'published_sources':sources,'latest_attempt':json.loads(status_path.read_text()) if status_path.exists() else None},indent=2))
    else:
        print(json.dumps(lookup(args.database, ccn=args.ccn, drg=args.drg, limit=args.limit), indent=2))
