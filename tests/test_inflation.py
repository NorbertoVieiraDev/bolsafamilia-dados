import json,sys,tempfile,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).parents[1]/'scripts'))
from inflation import attach
class InflationTests(unittest.TestCase):
 def test_latest_published_month_and_idempotent_monthly_factors(self):
  with tempfile.TemporaryDirectory() as t:
   root=Path(t);snapshot={'release':'original','requestedMonths':['202401','202402'],'cities':[{'code':'siafi-7107','uf':'SP'}],'coverage':{'202401':{},'202402':{}},'records':[{'city':'siafi-7107','month':'202401'},{'city':'siafi-7107','month':'202402'}]};(root/'snapshot.json').write_text(json.dumps(snapshot));(root/'source-manifest.json').write_text(json.dumps({'release':'original'}));raw=root/'ipca.json';raw.write_text(json.dumps([{'data':'01/01/2024','valor':'1'},{'data':'01/02/2024','valor':'10'},{'data':'01/03/2024','valor':'20'}]));release=attach(root,raw);s=json.loads((root/'snapshot.json').read_text());self.assertEqual(s['inflation']['baseMonth'],'202403');self.assertAlmostEqual(s['inflation']['factors']['202401'],1.32);self.assertAlmostEqual(s['inflation']['factors']['202402'],1.2);self.assertEqual(attach(root,raw),release)
