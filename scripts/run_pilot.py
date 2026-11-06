#!/usr/bin/env python3
"""One CGU municipality/month pilot; does not require a national catalog."""
import hashlib
import json
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from extract import Client, month, normalize_total, save


def main():
    city = os.environ.get('PILOT_CITY', '3550308')
    period = month(os.environ.get('PILOT_MONTH', '202601'))
    if not re.fullmatch(r'\d{7}', city):
        raise ValueError('PILOT_CITY must be a seven-digit IBGE code')
    if period > datetime.now(timezone.utc).strftime('%Y%m'):
        raise ValueError('Future months are not allowed')
    key = os.environ.get('PORTAL_TRANSPARENCIA_API_KEY')
    if not key:
        raise ValueError('Repository secret PORTAL_TRANSPARENCIA_API_KEY is missing or empty')
    root = Path(__file__).resolve().parents[1]
    output = root / 'work' / 'pilot'
    client = Client(key, root / 'work' / 'raw')
    rows = list(client.rows('totals', city, period, refresh=True))
    if len(rows) != 1:
        raise ValueError('Pilot must return exactly one municipal aggregate; empty data is not certified')
    row = normalize_total(rows[0], city, period)
    now = datetime.now(timezone.utc).isoformat()
    evidence = {'collectedAt': now, 'kind': 'municipal-aggregate-pilot', 'city': city,
                'month': period, 'responses': client.evidence}
    digest = hashlib.sha256(json.dumps(evidence, sort_keys=True).encode()).hexdigest()[:16]
    aggregate = {'scope': 'municipal-pilot', 'release': digest,
        'updatedAt': now, 'municipality': rows[0]['municipio'], 'record': row}
    save(output / 'municipal-aggregate.json', aggregate)
    save(output / 'provenance' / f'totals-{digest}.json', evidence)
    files = []
    for path in sorted(output.rglob('*.json')):
        if path.name == 'verification.json':
            continue
        files.append({'path': path.relative_to(output).as_posix(), 'bytes': path.stat().st_size,
                      'sha256': hashlib.sha256(path.read_bytes()).hexdigest()})
    verification = {'release': digest, 'city': city, 'month': period,
        'aggregateRows': 1, 'scopeValidated': True, 'nationalCoverageAssessed': False,
        'files': files, 'note': 'CGU authenticated pilot. The national IBGE catalog is not required or certified by this pilot.'}
    save(output / 'verification.json', verification)
    summary = (f'## Coleta piloto CGU\n\n'
               f'- Município IBGE: {city}\n- Mês: {period}\n'
               f'- Registros agregados: 1\n- Valor em centavos: {row["valueCents"]}\n'
               f'- Quantidade informada pela fonte: {row["beneficiaries"]}\n'
               f'- Versão: `{digest}`\n\n'
               'Autenticação e escopo da resposta CGU validados. Piloto limitado a um município/mês. '
               'Não é uma carga nacional e não depende da disponibilidade do catálogo IBGE. '
               'Nenhuma lista individual ou chave é incluída no artefato.\n')
    if os.environ.get('GITHUB_STEP_SUMMARY'):
        Path(os.environ['GITHUB_STEP_SUMMARY']).write_text(summary, encoding='utf-8')
    print('CGU authenticated pilot completed; one aggregate verified, original-byte hashes recorded.', flush=True)
    # Deliberately aggregate-only: enables durable public evidence without raw records or secrets.
    print('PILOT_EVIDENCE ' + json.dumps({'aggregate': aggregate, 'provenance': evidence, 'verification': verification}, ensure_ascii=False, separators=(',', ':')), flush=True)


if __name__ == '__main__':
    try:
        main()
    except (ValueError, RuntimeError) as exc:
        print(f'Pilot stopped: {exc}', file=sys.stderr)
        sys.exit(1)
