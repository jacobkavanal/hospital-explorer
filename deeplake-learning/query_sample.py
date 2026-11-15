"""Rank treatment groups by billed charges within the saved CMS sample."""
from pathlib import Path
import json
import deeplake

DATASET_PATH = str(Path(__file__).parent / 'cms_inpatient_sample')
QUERY = """
SELECT year, ccn, drg, avg_charges
WHERE avg_charges IS NOT NULL
ORDER BY avg_charges DESC, year, ccn, drg
LIMIT 5
"""


def main():
    ds = deeplake.open_read_only(DATASET_PATH)
    result = ds.query(QUERY)
    records = [
        {
            'year': int(result['year'][i]),
            'ccn': str(result['ccn'][i]),
            'drg': str(result['drg'][i]),
            'avg_charges': float(result['avg_charges'][i]),
        }
        for i in range(len(result))
    ]
    print('Highest average billed charges among the saved sample records:')
    print(json.dumps(records, indent=2))


if __name__ == '__main__':
    main()
