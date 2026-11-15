import unittest

from normalize import extract_ccn, normalize_ccn


class HospitalIdentityTests(unittest.TestCase):
    def test_preserves_leading_zero_and_trims_outer_whitespace(self):
        self.assertEqual(normalize_ccn(" 010001 "), "010001")

    def test_rejects_values_that_require_guessing_or_are_malformed(self):
        for value in [10001, "10001", "05A002", "", None, "０１０００１", "010 001"]:
            with self.subTest(value=value), self.assertRaises(ValueError):
                normalize_ccn(value)

    def test_all_three_field_names_resolve_without_changing_raw_records(self):
        examples = [
            ("hospital_general_information", {"facility_id": "010001"}),
            ("cost", {"Provider CCN": "010001"}),
            ("inpatient", {"Rndrng_Prvdr_CCN": "010001", "DRG_Cd": "003"}),
        ]
        for source, row in examples:
            with self.subTest(source=source):
                original = row.copy()
                self.assertEqual(extract_ccn(source, row), "010001")
                self.assertEqual(row, original)

    def test_missing_identifier_is_rejected(self):
        with self.assertRaises(ValueError):
            extract_ccn("cost", {"Net Patient Revenue": "100"})


if __name__ == "__main__":
    unittest.main()
