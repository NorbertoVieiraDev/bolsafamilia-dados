import importlib.util
import json
import tempfile
import unittest
from pathlib import Path
from decimal import Decimal

spec = importlib.util.spec_from_file_location('extract', Path(__file__).parents[1] / 'scripts/extract.py')
e = importlib.util.module_from_spec(spec)
spec.loader.exec_module(e)


class ExtractionTests(unittest.TestCase):
    def test_money_exact_and_invalid(self):
        self.assertEqual(e.cents(Decimal('123.45')), 12345)
        for value in ['NaN', '-1', '1.001', None]:
            with self.assertRaises(ValueError): e.cents(value)

    def test_month_range_and_inversion(self):
        self.assertEqual(list(e.months('202311', '202402')), ['202311', '202312', '202401', '202402'])
        for value in ['202313', '202302', 'n/a']:
            with self.assertRaises(ValueError): e.month(value)
        with self.assertRaises(ValueError): list(e.months('202501', '202401'))

    def test_mismatched_scope_rejected(self):
        row = {'municipio': {'codigoIBGE': '3550308'}, 'dataReferencia': '2026-01-01', 'valor': Decimal('600.00'), 'quantidadeBeneficiados': 1}
        self.assertEqual(e.normalize_total(row, '3550308', '202601')['valueCents'], 60000)
        with self.assertRaises(ValueError): e.normalize_total(row, '9999999', '202601')
        with self.assertRaises(ValueError): e.normalize_total(row, '3550308', '202602')

    def test_pagination_stops_only_on_empty_and_detects_repeats(self):
        with tempfile.TemporaryDirectory() as tmp:
            client = e.Client('synthetic-secret', tmp, 0)
            client.page = lambda kind,city,period,page,refresh: [{'id': page}] if page < 3 else []
            self.assertEqual(list(client.rows('totals','3550308','202601')), [{'id':1},{'id':2}])
            client.page = lambda *args: [{'id':1}]
            with self.assertRaises(ValueError): list(client.rows('totals','3550308','202601'))

    def test_homonyms_not_merged_and_identifiers_not_published(self):
        with tempfile.TemporaryDirectory() as tmp:
            records = [{'_key': '00000000001','name':'José Teste','month':'202601','competence':'202601','valueCents':60000},{'_key':'00000000002','name':'José Teste','month':'202601','competence':'202601','valueCents':50000},{'_key':'00000000001','name':'José Teste','month':'202602','competence':'202602','valueCents':65000}]
            e.publish_beneficiaries(records, '3550308', tmp, ['202601','202602','202603'])
            root = Path(tmp)/'beneficiaries'/'3550308'
            annual = json.loads((root/'2026'/'pages'/'1.json').read_text())
            self.assertEqual([r['valueCents'] for r in annual['rows']], [125000,50000])
            index = json.loads((root/'2026'/'index.json').read_text())
            self.assertEqual(index['months'], ['202601','202602','202603'])
            self.assertEqual(json.loads((root/'202603'/'index.json').read_text())['total'], 0)
            for p in Path(tmp).rglob('*.json'):
                body=p.read_text()
                self.assertNotIn('00000000001',body)
                self.assertNotIn('00000000002',body)
                self.assertNotIn('"_key"',body)
            self.assertEqual(e.search_name(' José da Silva '), 'JOSE DA SILVA')

    def test_duplicate_payment_rejected(self):
        r={'id':1,'municipio':{'codigoIBGE':'3550308'},'dataMesReferencia':'2026-01-01','dataMesCompetencia':'2026-01-01','beneficiarioNovoBolsaFamilia':{'nis':'00000000001','nome':'Teste'},'valorSaque':600}
        with self.assertRaises(ValueError): e.beneficiary_rows([r,r],'3550308','202601')

    def test_missing_credential_stops(self):
        with self.assertRaises(ValueError): e.Client(None,'unused')


if __name__ == '__main__': unittest.main()
