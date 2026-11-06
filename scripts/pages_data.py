#!/usr/bin/env python3
"""Publishable name/amount-only assets, sorted chunks and auditable bounds; no identifiers."""
import argparse,gzip,json,hashlib,shutil
from pathlib import Path
import duckdb
from bulk import sql,canonical,sha
from extract import save


def compact(path,data,compress=False):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    body=(json.dumps(data,ensure_ascii=False,separators=(',',':'))+'\n').encode()
    if compress:body=gzip.compress(body,compresslevel=6,mtime=0)
    path.write_bytes(body)
    return {'bytes':len(body),'sha256':hashlib.sha256(body).hexdigest()}


def generate(parquet,output,period,months,monthly=False,chunk_size=10000):
    out=Path(output);out.mkdir(parents=True,exist_ok=True)
    con=duckdb.connect();con.execute("SET memory_limit='4GB'");con.execute('SET threads=2');con.execute('SET preserve_insertion_order=false')
    spill=out.parent/'pages-spill';spill.mkdir(exist_ok=True);con.execute('SET temp_directory='+sql(spill))
    con.read_parquet(str(parquet)).create_view('p')
    if monthly:
        parts=out.parent/'monthly-people';parts.mkdir(exist_ok=True)
        for uf, in con.execute('SELECT DISTINCT uf FROM p ORDER BY uf').fetchall():
            query=f"SELECT siafi,coalesce(nis,'anonymous:'||source_row) person_key,arg_max(coalesce(name,'Não informado na fonte'),reference) AS name,sum(value_cents)::BIGINT value_cents FROM p WHERE uf={sql(uf)} GROUP BY siafi,person_key"
            con.execute(f"COPY ({query}) TO {sql(parts/(uf+'.parquet'))} (FORMAT PARQUET,COMPRESSION ZSTD)")
        people=f'SELECT * FROM read_parquet({sql(parts/"*.parquet")})'
    else:people='SELECT siafi,person_key,name,value_cents FROM p'
    con.sql(people).create_view('people')
    # DuckDB strips Latin accents consistently with the API's search normalization.
    cur=con.execute("SELECT siafi,name,value_cents,upper(strip_accents(name)) AS normalized_name FROM people ORDER BY siafi,normalized_name,name,person_key")
    current=None;buffer=[];chunks=[];city_sum=0;city_total=0;all_sum=0;all_count=0;city_count=0
    def flush():
        nonlocal buffer,chunks
        if not buffer:return
        name=f'{len(chunks)+1}.json.gz'
        meta=compact(out/current/name,buffer,True)
        chunks.append({'file':name,'first':buffer[0][2],'last':buffer[-1][2],'count':len(buffer),**meta});buffer=[]
    def finish():
        nonlocal city_count
        if current is None:return
        flush();compact(out/current/'index.json',{'city':current,'period':period,'months':months,'total':city_total,'valueCents':city_sum,'chunks':chunks})
        city_count+=1
    while rows:=cur.fetchmany(10000):
        for siafi,name,amount,normalized in rows:
            code='siafi-'+siafi
            if code!=current:
                finish();current=code;chunks=[];buffer=[];city_sum=0;city_total=0
            amount=int(amount);buffer.append([name,amount,normalized]);city_sum+=amount;city_total+=1;all_sum+=amount;all_count+=1
            if len(buffer)==chunk_size:flush()
    finish();con.close()
    if monthly:shutil.rmtree(parts)
    files=list(out.rglob('*'));files=[p for p in files if p.is_file()]
    if len(files)>19500:raise ValueError('Pages Free file bound exceeded; do not deploy or upgrade automatically')
    if any(p.stat().st_size>25*1024*1024 for p in files):raise ValueError('Pages individual asset bound exceeded')
    expected=duckdb.connect().execute('SELECT sum(value_cents) FROM read_parquet(?)',[str(parquet)]).fetchone()[0]
    if all_sum!=expected:raise ValueError('Names/amount data do not preserve source sums')
    report={'period':period,'months':months,'peopleRows':all_count,'valueCents':all_sum,'municipalities':city_count,'files':len(files),'bytes':sum(p.stat().st_size for p in files),'inputSha256':sha(parquet),'sourceIdentifiersPublished':False,'method':'Name/amount/search triples, sorted per municipality; 10000 records per gzip asset; prefix search uses chunk bounds.'}
    compact(out/'dataset.json',report);print(json.dumps(report),flush=True);return report


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--parquet',required=True);p.add_argument('--output',required=True);p.add_argument('--period',required=True);p.add_argument('--months',nargs='+',required=True);p.add_argument('--monthly',action='store_true');a=p.parse_args();generate(a.parquet,a.output,a.period,a.months,a.monthly)
