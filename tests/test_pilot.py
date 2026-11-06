import importlib.util
import io
import json
import os
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch

SCRIPTS = Path(__file__).parents[1] / 'scripts'
sys.path.insert(0, str(SCRIPTS))
spec = importlib.util.spec_from_file_location('run_pilot', SCRIPTS / 'run_pilot.py')
pilot = importlib.util.module_from_spec(spec)
spec.loader.exec_module(pilot)


class FakeClient:
    response = [{'municipio': {'codigoIBGE': '3550308', 'nomeIBGE': 'São Paulo'},
                 'dataReferencia': '2024-01-01', 'valor': 123.45, 'quantidadeBeneficiados': 10}]
    def __init__(self, key, raw):
        self.evidence = [{'url': 'https://api.portaldatransparencia.gov.br/api-de-dados/novo-bolsa-familia-por-municipio?mesAno=202401&codigoIbge=3550308&pagina=1', 'rows': 1, 'sha256': 'synthetic'}]
    def rows(self, *args, **kwargs):
        return self.response


class PilotTests(unittest.TestCase):
    def test_pilot_produces_only_aggregate_evidence_and_never_logs_secret(self):
        with tempfile.TemporaryDirectory() as tmp:
            env = {'PORTAL_TRANSPARENCIA_API_KEY': 'synthetic-key-do-not-log', 'PILOT_CITY': '3550308', 'PILOT_MONTH': '202401'}
            capture = io.StringIO()
            with patch.dict(os.environ, env, clear=True), patch.object(pilot, '__file__', str(Path(tmp)/'scripts/run_pilot.py')), patch.object(pilot, 'Client', FakeClient), redirect_stdout(capture):
                pilot.main()
            body = capture.getvalue()
            self.assertNotIn('synthetic-key-do-not-log', body)
            line = next(x for x in body.splitlines() if x.startswith('PILOT_EVIDENCE '))
            report = json.loads(line.removeprefix('PILOT_EVIDENCE '))
            self.assertEqual(report['aggregate']['record']['valueCents'], 12345)
            self.assertFalse(report['verification']['nationalCoverageAssessed'])
            self.assertTrue((Path(tmp)/'work/pilot/verification.json').exists())

    def test_empty_response_does_not_certify_authentication_or_data(self):
        class Empty(FakeClient):
            response = []
        with patch.dict(os.environ, {'PORTAL_TRANSPARENCIA_API_KEY': 'synthetic', 'PILOT_MONTH': '202401'}, clear=True), patch.object(pilot, 'Client', Empty):
            with self.assertRaises(ValueError): pilot.main()

    def test_missing_secret_is_detected_before_network(self):
        with patch.dict(os.environ, {}, clear=True):
            with self.assertRaisesRegex(ValueError, 'missing or empty'): pilot.main()
