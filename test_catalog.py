import unittest
from catalog import resolve, TITLES


def entry(source, year):
    return {'landingPage': {'title': TITLES[source]},
            'temporal': [{'endDate': f'{year}-12-31'}],
            'distribution': [
                {'format': 'API', 'description': 'latest', 'accessURL': 'ignored'},
                {'format': 'API', 'accessURL': f'https://data.cms.gov/data-api/v1/dataset/{source}-{year}/data'}]}


class CatalogTests(unittest.TestCase):
    def test_latest_common_year_not_latest_individual_year(self):
        result = resolve({'dataset': [entry('cost', 2024), entry('cost', 2025),
                                      entry('inpatient', 2024)]}, {})
        self.assertEqual(result['cost']['year'], 2024)
        self.assertEqual(result['inpatient']['dataset_id'], 'inpatient-2024')
        self.assertIsNone(result['hospital_general_information']['year'])

    def test_no_shared_year_fails(self):
        with self.assertRaisesRegex(ValueError, 'No common'):
            resolve({'dataset': [entry('cost', 2025), entry('inpatient', 2024)]}, {})
