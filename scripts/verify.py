#!/usr/bin/env python3
"""Offline release verification and aggregate-only output evidence; no deployment."""
import argparse
import hashlib
import json
from collections import defaultdict
from pathlib import Path
from extract import save


def verify(root):
    root = Path(root)
    snapshot = json.loads((root / 'snapshot.json').read_text())
    cities = {c['code'] for c in snapshot['cities']}
    if len(cities) != len(snapshot['cities']):
        raise ValueError('Duplicate cities')
    records, totals, seen = snapshot['records'], defaultdict(int), set()
    for r in records:
        key = (r['city'], r['month'])
        if key in seen or r['city'] not in cities or r['month'] not in snapshot['requestedMonths']:
            raise ValueError('Duplicate or unexpected scope')
        if any(type(r[f]) is not int or r[f] < 0 for f in ['valueCents', 'beneficiaries']):
            raise ValueError('Invalid metrics')
        seen.add(key)
        totals[r['month']] += r['valueCents']
    coverage = {}
    for m in snapshot['requestedMonths']:
        received = sum(1 for r in records if r['month'] == m)
        if snapshot['coverage'][m] != {'receivedCities': received, 'expectedCities': len(cities)}:
            raise ValueError('Incorrect coverage metadata')
        coverage[m] = {'receivedCities': received, 'expectedCities': len(cities), 'valueCents': totals[m]}
    detail = []
    for r in records:
        prefix = root / 'beneficiaries' / r['city'] / r['month']
        index_path = prefix / 'index.json'
        if not index_path.exists():
            continue
        index = json.loads(index_path.read_text())
        rows = []
        for page in range(1, index['pages'] + 1):
            rows.extend(json.loads((prefix / 'pages' / f'{page}.json').read_text())['rows'])
        if len(rows) != index['total']:
            raise ValueError('Incomplete beneficiary pages')
        value = sum(row['valueCents'] for row in rows)
        detail.append({'city': r['city'], 'month': r['month'], 'paymentRows': len(rows), 'detailCents': value, 'aggregateCents': r['valueCents'], 'equal': value == r['valueCents']})
    hashes = []
    for path in sorted(root.rglob('*.json')):
        if path.name == 'verification.json':
            continue
        hashes.append({'path': path.relative_to(root).as_posix(), 'bytes': path.stat().st_size, 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()})
    return {'release': snapshot['release'], 'coverage': coverage, 'completeGeography': all(v['receivedCities'] == len(cities) for v in coverage.values()), 'detailReconciliation': detail, 'note': 'Local-byte evidence, not CGU certification. Missing detail is not zero. Reconciliation mismatches require investigation.', 'files': hashes}


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('release_directory')
    p.add_argument('--report', default='work/verification.json')
    args = p.parse_args()
    report = verify(args.release_directory)
    save(args.report, report)
    print('Verification completed. Inspect coverage and reconciliation before hosting.')
