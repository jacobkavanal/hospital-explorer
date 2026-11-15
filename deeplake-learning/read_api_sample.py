"""Inspect five live CMS records before loading them into Deep Lake."""
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from fetch import fetch_page
from sources import SOURCES
from store import number


def read_sample():
    source = SOURCES['inpatient']
    page = fetch_page(
        'inpatient',
        raw_dir=Path(__file__).parent / 'raw',
        ccn='010001',
        page_size=5,
    )
    records = []
    for row in page.records:
        statuses = {}
        records.append({
            'year': source['year'],
            'ccn': row['Rndrng_Prvdr_CCN'],
            'drg': row['DRG_Cd'],
            'avg_charges': number(row, 'Avg_Submtd_Cvrd_Chrg', statuses),
        })
    return records


if __name__ == '__main__':
    for record in read_sample():
        print(record)
