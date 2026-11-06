#!/usr/bin/env python3
"""Reproducible CGU API collection. Standard library only; Python 3.10+."""
import argparse
import hashlib
import json
import os
import re
import time
import unicodedata
from collections import defaultdict
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

BASE = 'https://api.portaldatransparencia.gov.br/api-de-dados/'
CATALOG = 'https://servicodados.ibge.gov.br/api/v1/localidades/municipios?orderBy=nome'
ENDPOINTS = {'totals': 'novo-bolsa-familia-por-municipio', 'beneficiaries': 'novo-bolsa-familia-sacado-beneficiario-por-municipio'}


def save(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + '.tmp')
    tmp.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    tmp.replace(path)


def cents(value):
    try:
        d = Decimal(str(value))
        if not d.is_finite() or d < 0 or d != d.quantize(Decimal('.01')):
            raise ValueError('Invalid monetary value')
        return int(d * 100)
    except (InvalidOperation, TypeError):
        raise ValueError('Invalid monetary value') from None


def month(value):
    original = str(value)
    if re.fullmatch(r'\d{4}-\d{2}-\d{2}', original):
        datetime.strptime(original, '%Y-%m-%d')
        s = original.replace('-', '')[:6]
    elif re.fullmatch(r'\d{6}', original):
        s = original
    else:
        raise ValueError('Invalid month format')
    if not re.fullmatch(r'\d{6}', s) or not 1 <= int(s[4:]) <= 12 or s < '202303':
        raise ValueError('Month must be YYYYMM, from 202303')
    return s


def months(start, end):
    start, end = month(start), month(end)
    if start > end:
        raise ValueError('Start exceeds end')
    while start <= end:
        yield start
        y, m = int(start[:4]), int(start[4:])
        start = f'{y + (m == 12):04d}{m % 12 + 1:02d}'


class Client:
    def __init__(self, key, raw, delay=0.5, retries=5):
        if not key:
            raise ValueError('Configure PORTAL_TRANSPARENCIA_API_KEY; never pass the key as a CLI argument')
        self.key, self.raw, self.delay, self.retries = key, Path(raw), delay, retries
        self.last = 0
        self.evidence = []

    def page(self, kind, city, period, page, refresh=False):
        endpoint = ENDPOINTS[kind]
        params = {'mesAno': period, 'codigoIbge': city, 'pagina': page}
        url = BASE + endpoint + '?' + urlencode(params)
        path = self.raw / kind / city / period / f'{page}.json'
        cached = path.exists() and not refresh
        if cached:
            body = path.read_bytes()
        else:
            for attempt in range(self.retries + 1):
                time.sleep(max(0, self.delay - (time.monotonic() - self.last)))
                self.last = time.monotonic()
                try:
                    req = Request(url, headers={'chave-api-dados': self.key, 'Accept': 'application/json', 'User-Agent': 'DadosEmFoco-BolsaFamilia/0.1'})
                    with urlopen(req, timeout=60) as response:
                        body = response.read()
                    break
                except HTTPError as exc:
                    if exc.code not in (429, 500, 502, 503, 504) or attempt == self.retries:
                        raise RuntimeError(f'CGU HTTP {exc.code}; collection stopped, not treated as zero') from None
                    wait = exc.headers.get('Retry-After', '')
                    time.sleep(min(300, int(wait) if wait.isdigit() else 2 ** (attempt + 1)))
                except (URLError, TimeoutError):
                    if attempt == self.retries:
                        raise RuntimeError('CGU connection failed; collection stopped') from None
                    time.sleep(2 ** (attempt + 1))
        data = json.loads(body, parse_float=Decimal)
        if not isinstance(data, list):
            raise ValueError('CGU response is not an array')
        if not cached:
            path.parent.mkdir(parents=True, exist_ok=True)
            temp = path.with_suffix('.tmp')
            temp.write_bytes(body)
            temp.replace(path)
        self.evidence.append({'url': url, 'sha256': hashlib.sha256(body).hexdigest(), 'rows': len(data), 'cached': cached})
        return data

    def rows(self, kind, city, period, refresh=False):
        seen = set()
        for page in range(1, 100001):
            data = self.page(kind, city, period, page, refresh)
            if not data:
                return
            fingerprint = hashlib.sha256(json.dumps(data, sort_keys=True, default=str).encode()).hexdigest()
            if fingerprint in seen:
                raise ValueError('Repeated API page; pagination aborted')
            seen.add(fingerprint)
            yield from data
        raise ValueError('Page safety bound reached; collection incomplete')


def city_catalog(raw):
    out = []
    for r in raw:
        region = r.get('microrregiao')
        uf = region['mesorregiao']['UF'] if region else r['regiao-imediata']['regiao-intermediaria']['UF']
        out.append({'code': str(r['id']), 'name': r['nome'], 'uf': uf['sigla']})
    if len({r['code'] for r in out}) != len(out):
        raise ValueError('Duplicate IBGE city code')
    return sorted(out, key=lambda r: r['code'])


def normalize_total(row, city, period):
    if str(row['municipio']['codigoIBGE']) != city or month(row['dataReferencia']) != period:
        raise ValueError('API scope differs from request')
    n = row['quantidadeBeneficiados']
    if isinstance(n, bool) or not isinstance(n, int) or n < 0:
        raise ValueError('Invalid beneficiary count')
    return {'city': city, 'month': period, 'valueCents': cents(row['valor']), 'beneficiaries': n}


def beneficiary_rows(rows, city, period):
    out, seen = [], set()
    for r in rows:
        if str(r['municipio']['codigoIBGE']) != city or month(r['dataMesReferencia']) != period:
            raise ValueError('Beneficiary scope differs from request')
        record_id = str(r['id'])
        if record_id in seen:
            raise ValueError('Duplicate payment id')
        seen.add(record_id)
        person = r['beneficiarioNovoBolsaFamilia']
        identity = person.get('nis')
        if not identity or not re.fullmatch(r'\d{11}', str(identity)):
            raise ValueError('Missing unambiguous NIS; masked CPF cannot group homonyms')
        if not identity:
            raise ValueError('Missing stable identity for annual grouping')
        out.append({'_key': str(identity), 'name': person['nome'], 'month': period, 'competence': month(r['dataMesCompetencia']), 'valueCents': cents(r['valorSaque'])})
    return out


def search_name(name):
    return ''.join(c for c in unicodedata.normalize('NFKD', name.upper()) if not unicodedata.combining(c)).strip()


def publish_list(rows, city, period, out, covered_months=None):
    root = Path(out) / 'beneficiaries' / city / period
    rows = sorted(rows, key=lambda r: (-r['valueCents'], r['name']))
    metadata = {'city': city, 'period': period, 'total': len(rows), 'pageSize': 25, 'pages': (len(rows) + 24) // 25}
    if covered_months is not None:
        metadata['months'] = covered_months
    save(root / 'index.json', metadata)
    for i in range(0, len(rows), 25):
        save(root / 'pages' / f'{i // 25 + 1}.json', {'rows': rows[i:i + 25]})
    # Prefix buckets support server-side name search without loading a city/year.
    buckets = defaultdict(list)
    for row in rows:
        normalized = search_name(row['name'])
        key = normalized[:3].encode('utf-8').hex()
        buckets[key].append({**row, '_search': normalized})
    save(root / 'search-index.json', {'keys': sorted(buckets)})
    for key, entries in buckets.items():
        save(root / 'search' / f'{key}.json', {'rows': entries})


def publish_beneficiaries(records, city, out, periods=None):
    grouped = defaultdict(list)
    for period in periods or []:
        grouped[period] = []
    for r in records:
        grouped[r['month']].append(r)
    for period, rows in grouped.items():
        public = [{k: r[k] for k in ('name', 'month', 'competence', 'valueCents')} for r in rows]
        publish_list(public, city, period, out)
    annual = defaultdict(dict)
    for period in grouped:
        annual[period[:4]] = {}
    for r in records:
        people = annual[r['month'][:4]]
        entry = people.setdefault(r['_key'], {'name': r['name'], 'valueCents': 0})
        entry['valueCents'] += r['valueCents']
    for year, people in annual.items():
        publish_list(list(people.values()), city, year, out, sorted(m for m in grouped if m.startswith(year)))


def main():
    p = argparse.ArgumentParser(description=__doc__)
    sub = p.add_subparsers(dest='command', required=True)
    c = sub.add_parser('catalog')
    c.add_argument('--output', default='work/municipalities.json')
    c.add_argument('--input', help='Offline original JSON downloaded from the official IBGE URL')
    c = sub.add_parser('collect')
    c.add_argument('--catalog', default='work/municipalities.json')
    c.add_argument('--start', required=True)
    c.add_argument('--end', required=True)
    c.add_argument('--city', action='append', help='Repeat for a limited pilot. Omit to collect all catalog cities.')
    c.add_argument('--kind', choices=ENDPOINTS, default='totals')
    c.add_argument('--raw', default='work/raw')
    c.add_argument('--output', default='work/published')
    c.add_argument('--refresh', action='store_true', help='Refetch cached responses; preserves previous versioned release output')
    args = p.parse_args()
    if args.command == 'catalog':
        if args.input:
            body = Path(args.input).read_bytes()
        else:
            for attempt in range(4):
                try:
                    req = Request(CATALOG, headers={'User-Agent': 'DadosEmFoco-BolsaFamilia/0.1', 'Accept': 'application/json'})
                    with urlopen(req, timeout=60) as r:
                        body = r.read()
                    break
                except (HTTPError, URLError, TimeoutError):
                    if attempt == 3:
                        raise RuntimeError('IBGE unavailable; no catalog or zero counts were generated. Retry later or use catalog --input with the official original JSON.') from None
                    time.sleep(2 ** attempt)
        save(args.output, {'source': CATALOG, 'sha256': hashlib.sha256(body).hexdigest(), 'retrievedAt': datetime.now(timezone.utc).isoformat(), 'cities': city_catalog(json.loads(body))})
        return
    periods = list(months(args.start, args.end))
    catalog = json.loads(Path(args.catalog).read_text())
    by_code = {c['code']: c for c in catalog['cities']}
    cities = sorted(set(args.city or by_code))
    if not all(re.fullmatch(r'\d{7}', c) and c in by_code for c in cities):
        p.error('Unknown municipality; use codes from the downloaded IBGE catalog')
    client = Client(os.environ.get('PORTAL_TRANSPARENCIA_API_KEY'), args.raw)
    records = []
    for city in cities:
        people = []
        for period in periods:
            rows = list(client.rows(args.kind, city, period, args.refresh))
            if args.kind == 'totals':
                if len(rows) > 1:
                    raise ValueError('Unexpected multiple aggregate rows; inspect source before summing')
                if rows:
                    records.append(normalize_total(rows[0], city, period))
                # Empty is missing, never silently zero.
            else:
                people.extend(beneficiary_rows(rows, city, period))
        if args.kind == 'beneficiaries':
            publish_beneficiaries(people, city, args.output, periods)
    now = datetime.now(timezone.utc).isoformat()
    evidence = {'collectedAt': now, 'kind': args.kind, 'periods': periods, 'requestedCities': len(cities), 'expectedCities': len(by_code), 'responses': client.evidence}
    digest = hashlib.sha256(json.dumps(evidence, sort_keys=True).encode()).hexdigest()[:16]
    evidence['release'] = digest
    save(Path(args.output) / 'provenance' / f'{args.kind}-{digest}.json', evidence)
    if args.kind == 'totals':
        coverage = {m: {'receivedCities': len({r['city'] for r in records if r['month'] == m}), 'expectedCities': len(by_code)} for m in periods}
        snapshot = {'schemaVersion': 1, 'program': 'Novo Bolsa Família', 'release': digest, 'updatedAt': now, 'source': 'https://api.portaldatransparencia.gov.br/', 'requestedMonths': periods, 'cities': catalog['cities'], 'coverage': coverage, 'records': records}
        save(Path(args.output) / 'snapshot.json', snapshot)
    print(f'Collected {args.kind}; release {digest}. Output is outside Git; review before hosting.')


if __name__ == '__main__':
    main()
