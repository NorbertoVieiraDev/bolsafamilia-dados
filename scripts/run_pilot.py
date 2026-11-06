#!/usr/bin/env python3
"""Bounded authenticated pilot: one municipality, one month, aggregates only."""
import os
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from extract import month


def main():
    city = os.environ.get('PILOT_CITY', '3550308')
    period = month(os.environ.get('PILOT_MONTH', '202601'))
    if not re.fullmatch(r'\d{7}', city):
        raise ValueError('PILOT_CITY must be a seven-digit IBGE code')
    if period > datetime.now(timezone.utc).strftime('%Y%m'):
        raise ValueError('Future months are not allowed')
    if not os.environ.get('PORTAL_TRANSPARENCIA_API_KEY'):
        raise ValueError('Repository secret PORTAL_TRANSPARENCIA_API_KEY is missing or empty')
    root = Path(__file__).resolve().parents[1]
    def run(script, *args):
        subprocess.run([sys.executable, str(root / 'scripts' / script), *args], cwd=root, check=True)
    run('extract.py', 'catalog')
    run('extract.py', 'collect', '--start', period, '--end', period, '--city', city,
        '--output', 'work/pilot', '--refresh')
    run('verify.py', 'work/pilot', '--report', 'work/pilot/verification.json')
    import json
    snapshot = json.loads((root / 'work/pilot/snapshot.json').read_text())
    if len(snapshot['records']) != 1:
        raise ValueError('Pilot returned no municipal aggregate; do not certify empty results')
    row = snapshot['records'][0]
    summary = (f'## Coleta piloto CGU\n\n'
               f'- Município IBGE: {city}\n- Mês: {period}\n'
               f'- Registros agregados: 1\n- Valor em centavos: {row["valueCents"]}\n'
               f'- Quantidade informada pela fonte: {row["beneficiaries"]}\n'
               f'- Versão: `{snapshot["release"]}`\n\n'
               'Piloto limitado a um município/mês. Não é uma carga nacional. '
               'Nenhuma lista individual ou chave é incluída no artefato.\n')
    if os.environ.get('GITHUB_STEP_SUMMARY'):
        Path(os.environ['GITHUB_STEP_SUMMARY']).write_text(summary, encoding='utf-8')
    print('Pilot completed and verified; aggregate-only artifact ready.')


if __name__ == '__main__':
    try:
        main()
    except (ValueError, subprocess.CalledProcessError) as exc:
        print(f'Pilot stopped: {exc}', file=sys.stderr)
        sys.exit(1)
