"""Import a small CMS sample, skipping keys already stored locally."""
from pathlib import Path
import deeplake
from read_api_sample import read_sample

DATASET_PATH = str(Path(__file__).parent / 'cms_inpatient_sample')


def record_key(record):
    return (record['year'], record['ccn'], record['drg'])


def main():
    records = read_sample()
    if deeplake.exists(DATASET_PATH):
        ds = deeplake.open(DATASET_PATH)
    else:
        ds = deeplake.create(DATASET_PATH)
        ds.add_column('year', deeplake.types.Int32())
        ds.add_column('ccn', deeplake.types.Text())
        ds.add_column('drg', deeplake.types.Text())
        ds.add_column('avg_charges', deeplake.types.Float64())
        ds.commit()

    # Read only the identity columns when checking for duplicates.
    existing_keys = {
        (int(ds['year'][i]), str(ds['ccn'][i]), str(ds['drg'][i]))
        for i in range(len(ds))
    }
    new_records = []
    for record in records:
        key = record_key(record)
        if key not in existing_keys:
            new_records.append(record)
            existing_keys.add(key)

    if new_records:
        ds.append(new_records)
        ds.commit()

    saved = deeplake.open_read_only(DATASET_PATH)
    print(f'Fetched: {len(records)}')
    print(f'Added: {len(new_records)}')
    print(f'Skipped: {len(records) - len(new_records)}')
    print(f'Saved rows: {len(saved)}')


if __name__ == '__main__':
    main()
