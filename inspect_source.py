"""Display one fetched page; integration logic lives in fetch.py."""

import argparse
import json
from pathlib import Path

from fetch import fetch_page
from sources import SOURCES


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", choices=SOURCES)
    parser.add_argument("--ccn", help="Filter to one hospital; omit for all hospitals")
    parser.add_argument("--page-size", type=int, default=2)
    parser.add_argument("--offset", type=int, default=0)
    args = parser.parse_args()
    page = fetch_page(
        args.source,
        raw_dir=Path(__file__).parent / "data" / "raw",
        ccn=args.ccn,
        page_size=args.page_size,
        offset=args.offset,
    )
    print(json.dumps(page.records, indent=2))
    print(f"Rows in this page: {len(page.records)}; API total: {page.total_count}")
    print(f"Raw evidence: {page.capture_dir}")
    print("Single page only; completeness has not been established.")


if __name__ == "__main__":
    main()
