import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import Mock

from fetch import FetchedPage
from ingest import all_pages
from query import lookup
from refresh import refresh
from store import number


PROFILE = {'facility_id':'010001','facility_name':'Fixture Hospital','state':'AL','hospital_overall_rating':'4'}
COST = {'Provider CCN':'010001','rpt_rec_num':'10','Fiscal Year Begin Date':'2024-01-01','Fiscal Year End Date':'2024-12-31',
        'Net Patient Revenue':'100','Less Total Operating Expense':'110','Net Income from Service to Patients':'-10'}
INPATIENT = {'Rndrng_Prvdr_CCN':'010001','DRG_Cd':'003','DRG_Desc':'Fixture DRG','Tot_Dschrgs':'12',
             'Avg_Submtd_Cvrd_Chrg':'20','Avg_Tot_Pymt_Amt':'10','Avg_Mdcr_Pymt_Amt':''}
CONTRACTS = {name:{'dataset_id':name,'year':None if name=='hospital_general_information' else 2024,'metadata':{}} for name in ['hospital_general_information','cost','inpatient']}


def fixture_pages(source, contract, directory):
    row = {'hospital_general_information':PROFILE,'cost':COST,'inpatient':INPATIENT}[source]
    yield FetchedPage(source,[row],Path(directory),0,500,None)


class PaginationTests(unittest.TestCase):
    def test_short_data_page_does_not_stop_before_terminal_page(self):
        fetcher=Mock(side_effect=[
            FetchedPage('cost',[{'rpt_rec_num':'1'}],Path('a'),0,5000,None),
            FetchedPage('cost',[{'rpt_rec_num':'2'}],Path('b'),1,5000,None),
            FetchedPage('cost',[],Path('c'),2,5000,None)])
        result=list(all_pages('cost',{'family':'data'},Path('raw'),fetcher=fetcher))
        self.assertEqual(sum(len(p.records) for p in result),2)
        self.assertEqual([c.kwargs['offset'] for c in fetcher.call_args_list],[0,1,2])

    def test_repeated_page_is_rejected(self):
        page=FetchedPage('cost',[{'rpt_rec_num':'1'}],Path('a'),0,5000,None)
        with self.assertRaisesRegex(ValueError,'Repeated'):
            list(all_pages('cost',{'family':'data'},Path('raw'),fetcher=Mock(return_value=page)))

    def test_profile_premature_end_is_rejected(self):
        fetcher=Mock(side_effect=[FetchedPage('profile',[{'facility_id':'010001'}],Path('a'),0,500,2),
                                FetchedPage('profile',[],Path('b'),1,500,2)])
        with self.assertRaisesRegex(ValueError,'incomplete'):
            list(all_pages('hospital_general_information',{'family':'profile'},Path('raw'),fetcher=fetcher))


class PipelineTests(unittest.TestCase):
    def test_publish_repeat_query_and_failure_preservation(self):
        with TemporaryDirectory() as directory:
            root=Path(directory)
            first=refresh(root,resolver=lambda _:CONTRACTS,pages=fixture_pages)
            rows=lookup(root/'hospital.sqlite',ccn='010001',drg='003')
            self.assertEqual(len(rows),1)
            self.assertEqual(rows[0]['inpatient_year'],2024)
            self.assertIsNone(rows[0]['avg_medicare_payment'])
            self.assertEqual(rows[0]['income_patient_services'],-10)
            second=refresh(root,resolver=lambda _:CONTRACTS,pages=fixture_pages)
            self.assertEqual(second['sources']['inpatient']['changes']['unchanged'],1)
            old=(root/'hospital.sqlite').read_bytes()
            def fail(source,contract,directory):
                if source=='cost': raise RuntimeError('fixture network failure')
                yield from fixture_pages(source,contract,directory)
            with self.assertRaisesRegex(RuntimeError,'fixture network'):
                refresh(root,resolver=lambda _:CONTRACTS,pages=fail)
            self.assertEqual((root/'hospital.sqlite').read_bytes(),old)
            self.assertEqual(lookup(root/'hospital.sqlite'),rows)
            self.assertEqual(json.loads((root/'status.json').read_text())['state'],'failed')

    def test_duplicate_reports_are_ambiguous_without_multiplication(self):
        def extra(source,contract,directory):
            yield from fixture_pages(source,contract,directory)
            if source=='cost':
                yield FetchedPage(source,[{**COST,'rpt_rec_num':'11'}],Path(directory),1,500,None)
        with TemporaryDirectory() as directory:
            refresh(directory,resolver=lambda _:CONTRACTS,pages=extra)
            rows=lookup(Path(directory)/'hospital.sqlite')
            self.assertEqual(len(rows),1)
            self.assertEqual(rows[0]['cost_status'],'ambiguous')
            self.assertIsNone(rows[0]['net_revenue'])

    def test_numeric_zero_missing_and_invalid_are_distinct(self):
        status={}
        self.assertEqual(number({'x':'0'},'x',status),0)
        self.assertIsNone(number({'x':''},'x',status))
        self.assertEqual(status,{'x':''})
        for value in ['garbage','NaN','Infinity']:
            with self.assertRaises(ValueError): number({'x':value},'x',{})


if __name__=='__main__': unittest.main()
