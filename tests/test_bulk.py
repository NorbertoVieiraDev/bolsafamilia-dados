import importlib.util,sys,tempfile,unittest,zipfile,json,io,csv
from pathlib import Path
sys.path.insert(0,str(Path(__file__).parents[1]/'scripts'))
try:
 import duckdb
 import bulk
except ImportError:bulk=None

@unittest.skipIf(bulk is None,'Install requirements.txt for bulk tests')
class BulkTests(unittest.TestCase):
 def archive(self,root,period,rows):
  out=io.StringIO(newline='');w=csv.writer(out,delimiter=';');w.writerow(['MÊS COMPETÊNCIA','MÊS REFERÊNCIA','UF','CÓDIGO MUNICÍPIO SIAFI','NOME MUNICÍPIO','CPF FAVORECIDO','NIS FAVORECIDO','NOME FAVORECIDO','VALOR PARCELA']);w.writerows(rows)
  with zipfile.ZipFile(root/(period+'.zip'),'w',zipfile.ZIP_DEFLATED) as z:z.writestr(period+'.csv',out.getvalue().encode('cp1252'))
 def test_missing_nis_is_not_merged_and_retroactive_rows_are_included(self):
  with tempfile.TemporaryDirectory() as t:
   root=Path(t);self.archive(root,'202601',[['202601','202512','SP','7107','SÃO PAULO','','00000000001','Nome sintético','600,00'],['202601','202601','SP','7107','SÃO PAULO','','00000000001','Nome sintético','100,00'],['202601','202601','SP','7107','SÃO PAULO','','','Não informado','200,00'],['202601','202601','SP','7107','SÃO PAULO','','','Não informado','300,00']])
   r=bulk.process_month('202601',root,fold=True)
   self.assertEqual(r['valueCents'],120000);self.assertEqual(r['sourceRows'],4);self.assertEqual(r['records'][0]['beneficiaries'],3)
   con=duckdb.connect();rows=con.execute('SELECT count(*),sum(value_cents) FROM read_parquet(?)',[str(root/'annual/2026.parquet')]).fetchone();self.assertEqual(rows,(3,120000));con.close()
   self.assertEqual(bulk.process_month('202601',root,fold=True)['zipSha256'],r['zipSha256'])
   bulk.history(root,['202601'],root/'published');body=(root/'published/snapshot.json').read_text();self.assertNotIn('Nome sintético',body);self.assertNotIn('00000000001',body)
 def test_scope_mismatch_fails_instead_of_silently_filtering(self):
  with tempfile.TemporaryDirectory() as t:
   root=Path(t);self.archive(root,'202601',[['202512','202512','SP','7107','SÃO PAULO','','00000000001','Nome sintético','600,00']])
   with self.assertRaises(ValueError):bulk.process_month('202601',root,fold=False)
