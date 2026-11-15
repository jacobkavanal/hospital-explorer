# NRP and Deep Lake progress

## NRP preparation

- Signed in through UCSD and verified that `kubectl` works locally.
- Learned how namespaces organize team resources, Jobs manage tasks that finish, and Pods run containers.
- Learned how a PersistentVolumeClaim requests storage so saved datasets can survive Pod removal.
- Awaiting project namespace access before testing workloads on NRP.

## Deep Lake exercise

- Built a local Python script that fetches five real CMS inpatient records through our existing API fetcher, which also preserves raw responses.
- Defined typed columns for release year, CCN, DRG, and average charges, keeping identifiers as text to preserve leading zeros.
- Used `(year, CCN, DRG)` as the record key and checked existing keys before appending records.
- Saved the dataset with `commit()` and reopened it read-only to verify persistence.
- Verified that a second import added zero rows and skipped all five existing records. This currently prevents duplicates but does not apply corrections to existing records.

## Querying the saved data

- `query_sample.py` reads the Deep Lake dataset stored locally in `deeplake-learning/cms_inpatient_sample/`.
- The import fetches CMS records, maps selected fields, then saves them with `append()` and `commit()`.
- The query opens that saved dataset with `deeplake.open_read_only(DATASET_PATH)` and runs `ds.query(QUERY)` against it.
- Querying does not call CMS or read our SQLite database. It returns the records as they were saved during import.
- Raw API responses remain separate in `deeplake-learning/raw/` for inspection.
- The query ranks average charges within five saved 2023 records from hospital `010001`, across different DRGs. It does not rank hospitals nationally.
- Verified the result against an independent Python sort of the stored values and confirmed the dataset version stayed unchanged.
- Rerunning the import checks for new keys, but currently skips corrected values for existing keys.

```bash
cd /Users/jacob/school/hospital-explorer/deeplake-learning
.venv/bin/python query_sample.py
```

## Potential value for the full project

- Dataset versioning could help researchers reproduce an analysis using the same saved data version. This is a next feature to test.
- Support for richer data, including images and embeddings, could become useful if the project expands beyond hospital tables.
- Cloud-storage support could let workloads on NRP access shared datasets, once storage and permissions are configured.
- The exercise tests ingestion and repeatability before expanding to larger datasets. It does not yet demonstrate shared deployment or performance at scale.
- SQLite already supports our current relational joins well. We still need to evaluate which parts belong in Deep Lake and which should remain in a relational database.

## Next steps

- Extend query verification to compare saved values with the captured source responses.
- Test version history and define how imports should handle corrected records.
- Once namespace access is available, run a small containerized workload on NRP with persistent storage.
