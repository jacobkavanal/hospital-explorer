"""Complete, bounded pagination using the existing single-page fetcher."""

import hashlib
import json

from fetch import fetch_page


def natural_key(source, row):
    if source == "hospital_general_information":
        return (row["facility_id"],)
    if source == "cost":
        return (row["rpt_rec_num"],)
    return (row["Rndrng_Prvdr_CCN"], row["DRG_Cd"])


def all_pages(source, contract, raw_dir, *, fetcher=fetch_page, max_rows=1000000):
    offset, expected = 0, None
    page_hashes, keys = set(), set()
    size = 500 if contract["family"] == "profile" else 5000
    while True:
        page = fetcher(source, contract=contract, raw_dir=raw_dir, page_size=size, offset=offset)
        if page.total_count is not None:
            if expected is not None and expected != page.total_count:
                raise ValueError("Total count changed during pagination")
            expected = page.total_count
        if not page.records:
            if offset == 0 or (expected is not None and offset != expected):
                raise ValueError("Empty or incomplete source extract")
            yield page  # Preserve the terminal page's evidence too.
            return
        digest = hashlib.sha256(json.dumps(page.records, sort_keys=True).encode()).hexdigest()
        if digest in page_hashes:
            raise ValueError("Repeated page: offset may have been ignored")
        page_hashes.add(digest)
        for row in page.records:
            key = natural_key(source, row)
            if any(not isinstance(v, str) or not v for v in key) or key in keys:
                raise ValueError(f"Invalid or duplicate natural key: {source} {key}")
            keys.add(key)
        offset += len(page.records)
        if offset > max_rows or (expected is not None and offset > expected):
            raise ValueError("Row count exceeded expected total or safety cap")
        yield page
        if expected is not None and offset == expected:
            return
