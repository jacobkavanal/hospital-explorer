"""Offline contract tests; live API checks are separate."""

import hashlib
import io
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

import requests

from fetch import fetch_page


class FetchTests(unittest.TestCase):
    def setUp(self):
        self.directory = TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.raw_dir = Path(self.directory.name) / "raw"

    def response(self, payload, status=200):
        response = requests.Response()
        response.status_code = status
        response._content = json.dumps(payload).encode()
        response.url = "https://example.invalid/offline-fixture"
        return response

    def test_data_sources_use_correct_filters_and_preserve_records(self):
        for name, field in [("cost", "Provider CCN"), ("inpatient", "Rndrng_Prvdr_CCN")]:
            with self.subTest(source=name):
                records = [{field: "010001", "fixture_missing_amount": None}]
                response = self.response(records)
                with patch("fetch.requests.get", return_value=response) as get, patch(
                    "sys.stdout", new_callable=io.StringIO
                ) as output:
                    page = fetch_page(name, raw_dir=self.raw_dir, ccn="010001", page_size=2, offset=4)
                self.assertEqual(output.getvalue(), "")
                self.assertEqual(get.call_args.kwargs["params"], {
                    "size": 2, "offset": 4, f"filter[{field}]": "010001",
                })
                self.assertEqual(page.records, records)
                self.assertEqual(page.offset, 4)
                self.assertIsNone(page.total_count)
                self.assertEqual((page.capture_dir / "response.json").read_bytes(), response.content)
                manifest = json.loads((page.capture_dir / "manifest.json").read_text())
                self.assertEqual(manifest["sha256"], hashlib.sha256(response.content).hexdigest())
                self.assertEqual(manifest["scope"]["coverage"], "single_page")
                self.assertEqual(manifest["scope"]["year"], 2023)

    def test_profile_has_its_own_query_and_response_contract(self):
        records = [{"facility_id": "010001"}]
        with patch("fetch.requests.get", return_value=self.response({"results": records, "count": 1})) as get:
            page = fetch_page("hospital_general_information", raw_dir=self.raw_dir, ccn="010001", page_size=2)
        self.assertEqual(get.call_args.kwargs["params"], {
            "limit": 2, "offset": 0, "conditions[0][property]": "facility_id",
            "conditions[0][value]": "010001", "conditions[0][operator]": "=",
        })
        self.assertEqual(page.records, records)
        self.assertEqual(page.total_count, 1)

    def test_empty_page_is_returned_without_inventing_a_total_count(self):
        with patch("fetch.requests.get", return_value=self.response([])):
            page = fetch_page("cost", raw_dir=self.raw_dir, offset=20)
        self.assertEqual(page.records, [])
        self.assertIsNone(page.total_count)

    def test_bad_responses_fail_but_keep_raw_evidence(self):
        cases = [
            ("cost", {"results": []}, "array of records"),
            ("cost", [{"Provider CCN": "050002"}], "unexpected hospital"),
            ("cost", [{"Provider CCN": "10001"}], "six-character"),
            ("cost", [None], "record to be an object"),
            ("cost", [{"Provider CCN": "010001"}] * 3, "page size"),
            ("hospital_general_information", {"results": [], "count": "unknown"}, "profile count"),
        ]
        for source, payload, message in cases:
            with self.subTest(payload=payload):
                before = len(list(self.raw_dir.glob("*/response.json")))
                with patch("fetch.requests.get", return_value=self.response(payload)):
                    with self.assertRaisesRegex(ValueError, message):
                        fetch_page(source, raw_dir=self.raw_dir, ccn="010001", page_size=2)
                self.assertEqual(len(list(self.raw_dir.glob("*/response.json"))), before + 1)

    def test_invalid_json_keeps_evidence(self):
        response = self.response(None)
        response._content = b"not JSON"
        with patch("fetch.requests.get", return_value=response):
            with self.assertRaisesRegex(ValueError, "raw evidence"):
                fetch_page("cost", raw_dir=self.raw_dir)
        self.assertEqual(len(list(self.raw_dir.glob("*/response.json"))), 1)

    def test_connection_and_http_failures_return_no_page(self):
        with patch("fetch.requests.get", side_effect=requests.ConnectTimeout):
            with self.assertRaises(requests.ConnectTimeout):
                fetch_page("cost", raw_dir=self.raw_dir)
        with patch("fetch.requests.get", return_value=self.response({"error": "failure"}, 500)):
            with self.assertRaises(requests.HTTPError):
                fetch_page("cost", raw_dir=self.raw_dir)
        self.assertFalse(self.raw_dir.exists())

    def test_bad_arguments_fail_before_network_access(self):
        for kwargs in [{"page_size": 0}, {"page_size": 5001}, {"offset": -1}, {"ccn": "10001"}]:
            with self.subTest(kwargs=kwargs), patch("fetch.requests.get") as get:
                with self.assertRaises(ValueError):
                    fetch_page("cost", raw_dir=self.raw_dir, **kwargs)
                get.assert_not_called()


if __name__ == "__main__":
    unittest.main()
