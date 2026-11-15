"""Source contracts shared by retrieval and normalization.

Historical IDs are defaults for the manual inspection tool. Complete refreshes
resolve the latest common year through catalog.py and override these contracts.
"""

SOURCES = {
    "hospital_general_information": {
        "family": "profile",
        "dataset_id": "xubh-q36u",
        "ccn_field": "facility_id",
        "year": None,  # Current profile, not historical 2023 quality.
    },
    "cost": {
        "family": "data",
        "dataset_id": "f08d4c46-c0e4-4bcb-a54a-c62c87d59251",
        "ccn_field": "Provider CCN",
        "year": 2023,
    },
    "inpatient": {
        "family": "data",
        "dataset_id": "2f1e57ea-ac2f-4f62-aeb1-f8254307c395",
        "ccn_field": "Rndrng_Prvdr_CCN",
        "year": 2023,
    },
}
