#!/usr/bin/env python3
"""Attach official SGS 433 monthly IPCA factors; apply each source month before annual sums."""
import argparse,hashlib,json
from decimal import Decimal
from pathlib import Path
from extract import save

SOURCE='https://api.bcb.gov.br/dados/serie/bcdata.sgs.433/dados?formato=json&dataInicial=01/03/2023&dataFinal=30/09/2026'

def attach(history,original):
    root=Path(history);path=root/'snapshot.json';snapshot=json.loads(path.read_text());raw=Path(original).read_bytes();rates={}
    for row in json.loads(raw):
        day,month,year=row['data'].split('/');key=year+month
        value=Decimal(row['valor'])
        if key in rates or not value.is_finite() or not -100<value<100:raise ValueError('Invalid or duplicate official monthly rate')
        rates[key]=value
    periods=snapshot['requestedMonths'];base=max(periods)
    # Every link between a source month and the reference month must be present.
    factor=Decimal(1);factors={}
    for period in reversed(periods):
        factors[period]=float(factor)
        if period not in rates:raise ValueError('Missing IPCA month '+period)
        factor*=1+rates[period]/100
    sha=hashlib.sha256(raw).hexdigest()
    snapshot['inflation']={'baseMonth':base,'source':SOURCE,'sourceSha256':sha,'monthlyRates':{m:str(rates[m]) for m in periods},'factors':factors,'method':'For payment month m, multiply by the product of 1+monthly IPCA from m+1 through the base month; round each monthly municipal amount to cents before annual sums.'}
    old=snapshot['release'];snapshot['release']=hashlib.sha256((old+sha+'source-geography-v1').encode()).hexdigest()[:16]
    # Source-file geography counts, rather than a current municipality list, respect new municipalities.
    for m in periods:
        rows=[r for r in snapshot['records'] if r['month']==m];catalog={c['code']:c for c in snapshot['cities']};by_uf={}
        for r in rows:
            uf=catalog[r['city']]['uf'];by_uf[uf]=by_uf.get(uf,0)+1
        snapshot['coverage'][m]['expectedByUf']=by_uf
    snapshot['detailPeriods']=sorted({m[:4] for m in periods})+[base]
    path.write_text(json.dumps(snapshot,ensure_ascii=False,separators=(',',':'))+'\n')
    manifest=json.loads((root/'source-manifest.json').read_text());manifest['release']=snapshot['release'];manifest['inflation']={k:v for k,v in snapshot['inflation'].items() if k not in ('factors','monthlyRates')};manifest['snapshotSha256']=hashlib.sha256(path.read_bytes()).hexdigest();save(root/'source-manifest.json',manifest)
    return snapshot['release']

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--history',required=True);p.add_argument('--original',required=True);a=p.parse_args();print(attach(a.history,a.original))
