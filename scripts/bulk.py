#!/usr/bin/env python3
"""Official monthly ZIPs -> audited national series and local annual name/amount tables.
DuckDB 1.4.3. No credentials; raw ZIP/CSV/Parquet must stay outside Git.
"""
import argparse
import concurrent.futures
import csv
import hashlib
import io
import json
import os
import re
import shutil
import time
import unicodedata
import urllib.error
import urllib.request
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from extract import months, save


def sha(path):
    with open(path,'rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()


def sql(value):
    return "'"+str(value).replace("'","''")+"'"


def canonical(s):
    return ''.join(c for c in unicodedata.normalize('NFKD',s.upper()) if not unicodedata.combining(c)).strip()


HEADERS={'MES COMPETENCIA':'competence','MES REFERENCIA':'reference','UF':'uf','CODIGO MUNICIPIO SIAFI':'siafi','NOME MUNICIPIO':'city_name','CPF FAVORECIDO':'cpf','NIS FAVORECIDO':'nis','NOME FAVORECIDO':'name','VALOR PARCELA':'value','DATA DISPONIBILIZACAO':'available_date'}


def download(period,root):
    url=f'https://portaldatransparencia.gov.br/download-de-dados/novo-bolsa-familia/{period}'
    path=root/f'{period}.zip'
    if path.exists() and zipfile.is_zipfile(path):return path,url
    for attempt in range(3):
        try:
            req=urllib.request.Request(url,headers={'User-Agent':'DadosEmFoco-BolsaFamilia/0.2'})
            with urllib.request.urlopen(req,timeout=90) as response,open(path.with_suffix('.part'),'wb') as f:
                shutil.copyfileobj(response,f,4*1024*1024)
            if not zipfile.is_zipfile(path.with_suffix('.part')):raise ValueError('Official download is not a ZIP')
            path.with_suffix('.part').replace(path)
            return path,url
        except (urllib.error.URLError,TimeoutError):
            if attempt==2:raise
            time.sleep(2**attempt)


def process_month(period,root,fold=True,keep_parquet=False):
    import duckdb
    started=time.monotonic()
    report_path=root/'aggregates'/f'{period}.json'
    state=root/'annual'/f'{period[:4]}.parquet'
    checkpoint=root/'annual'/f'{period[:4]}-months.json'
    done=json.loads(checkpoint.read_text()) if checkpoint.exists() else []
    if report_path.exists() and (not fold or period in done):
        print(json.dumps({'month':period,'status':'cached'}),flush=True)
        return json.loads(report_path.read_text())
    archive,url=download(period,root)
    zip_hash=sha(archive)
    csv_path=root/f'{period}.csv'
    with zipfile.ZipFile(archive) as z:
        members=[m for m in z.infolist() if m.filename.lower().endswith('.csv')]
        if len(members)!=1:raise ValueError('Expected exactly one CSV member')
        member=members[0]
        with z.open(member) as f:
            reader=io.TextIOWrapper(f,encoding='cp1252',newline='')
            original_header=next(csv.reader([reader.readline()],delimiter=';'))
            columns=[HEADERS.get(canonical(h)) for h in original_header]
            if None in columns or len(set(columns))!=len(columns) or not (set(HEADERS.values())-{'available_date'})<=set(columns):
                raise ValueError('Unexpected official CSV schema')
            with open(csv_path,'w',encoding='utf-8',newline='') as out:
                csv.writer(out,delimiter=';').writerow(columns)
                while chunk:=reader.read(4*1024*1024):out.write(chunk)
        crc=member.CRC
    parquet=root/f'{period}.parquet'
    con=duckdb.connect()
    con.execute("SET memory_limit='5GB'")
    con.execute('SET threads=2')
    con.execute('SET preserve_insertion_order=false')
    temp=root/'spill'/period;temp.mkdir(parents=True,exist_ok=True)
    con.execute('SET temp_directory='+sql(temp))
    defs='{'+','.join(sql(c)+":'VARCHAR'" for c in columns)+'}'
    con.sql(f"SELECT * FROM read_csv({sql(csv_path)},header=true,delim=';',columns={defs},strict_mode=true)").create_view('raw')
    invalid=con.sql(f"SELECT count(*) FROM raw WHERE competence IS DISTINCT FROM {sql(period)} OR NOT regexp_full_match(coalesce(uf,''),'[A-Z]{{2}}') OR NOT regexp_full_match(coalesce(siafi,''),'[0-9]{{4,5}}') OR NOT regexp_full_match(coalesce(value,''),'[0-9]+(,[0-9]{{2}})?')").fetchone()[0]
    if invalid:raise ValueError(f'Invalid scope/geography/money in {invalid} source rows')
    con.execute(f"COPY (SELECT competence,reference,uf,siafi,city_name,nullif(nis,'') nis,name,CAST(CAST(replace(value,',','.') AS DECIMAL(18,2))*100 AS BIGINT) value_cents,row_number() OVER() source_row FROM raw) TO {sql(parquet)} (FORMAT PARQUET,COMPRESSION ZSTD,ROW_GROUP_SIZE 100000)")
    csv_path.unlink()
    con.read_parquet(str(parquet)).create_view('payments')
    summary=con.sql('SELECT count(*),sum(value_cents),count(*) FILTER(WHERE nis IS NULL),min(reference),max(reference) FROM payments').fetchone()
    rows=con.sql("SELECT siafi,uf,arg_max(city_name,source_row),sum(value_cents)::BIGINT,count(DISTINCT nis)+count(*) FILTER(WHERE nis IS NULL),count(*) FROM payments GROUP BY siafi,uf ORDER BY siafi").fetchall()
    records=[{'city':'siafi-'+r[0],'uf':r[1],'name':r[2],'month':period,'valueCents':int(r[3]),'beneficiaries':r[4],'paymentRows':r[5]} for r in rows]
    if sum(r['valueCents'] for r in records)!=int(summary[1]) or sum(r['paymentRows'] for r in records)!=summary[0]:raise ValueError('Aggregation reconciliation failed')
    result={'month':period,'source':url,'zipSha256':zip_hash,'zipBytes':archive.stat().st_size,'csvMember':member.filename,'csvCRC32':f'{crc:08x}','sourceRows':summary[0],'valueCents':int(summary[1]),'missingNisRows':summary[2],'referenceRange':[summary[3],summary[4]],'municipalities':len(records),'beneficiaryMethod':'distinct non-null NIS per municipality plus each row without NIS; API reconciliation required','records':records}
    save(report_path,result)
    if fold and period not in done:
        # Aggregate one UF at a time to bound exact identity grouping memory.
        state.parent.mkdir(parents=True,exist_ok=True)
        target=state.with_suffix('.next.parquet')
        parts=root/'annual'/f'{period}-parts'
        parts.mkdir(parents=True,exist_ok=True)
        if state.exists():con.read_parquet(str(state)).create_view('previous_people')
        for uf in sorted({r['uf'] for r in records}):
            current=f"SELECT uf,siafi,coalesce(nis,'anonymous:{period}:'||source_row) person_key,arg_max(coalesce(name,'Não informado na fonte'),reference) AS name,sum(value_cents)::BIGINT value_cents,{sql(period)} last_month FROM payments WHERE uf={sql(uf)} GROUP BY uf,siafi,person_key"
            if state.exists():
                query=f"SELECT uf,siafi,person_key,arg_max(name,last_month) AS name,sum(value_cents)::BIGINT value_cents,max(last_month) last_month FROM (SELECT * FROM previous_people WHERE uf={sql(uf)} UNION ALL {current}) GROUP BY uf,siafi,person_key"
            else:query=current
            con.execute(f"COPY ({query}) TO {sql(parts/(uf+'.parquet'))} (FORMAT PARQUET,COMPRESSION ZSTD,ROW_GROUP_SIZE 100000)")
        con.execute(f"COPY (SELECT * FROM read_parquet({sql(parts/'*.parquet')})) TO {sql(target)} (FORMAT PARQUET,COMPRESSION ZSTD,ROW_GROUP_SIZE 100000)")
        check=con.sql(f'SELECT sum(value_cents) FROM read_parquet({sql(target)})').fetchone()[0]
        expected=sum(json.loads(p.read_text())['valueCents'] for p in (root/'aggregates').glob(period[:4]+'*.json'))
        if check!=expected:raise ValueError('Annual person table value reconciliation failed')
        state_sum=sha(target)
        target.replace(state)
        save(checkpoint,sorted(done+[period]))
        shutil.rmtree(parts)
        save(state.with_suffix('.audit.json'),{'year':period[:4],'months':sorted(done+[period]),'valueCents':int(check),'sha256':state_sum,'bytes':state.stat().st_size})
    con.close()
    if not keep_parquet:parquet.unlink(missing_ok=True)
    shutil.rmtree(temp,ignore_errors=True)
    print(json.dumps({'month':period,'rows':summary[0],'municipalities':len(records),'seconds':round(time.monotonic()-started,1)}),flush=True)
    return result


def history(root,periods,output):
    docs=[json.loads((root/'aggregates'/f'{m}.json').read_text()) for m in periods]
    catalog={}
    for d in docs:
        for r in d['records']:catalog[r['city']]={'code':r['city'],'name':r['name'],'uf':r['uf'],'sourceCodeSystem':'SIAFI'}
    rows=[{k:r[k] for k in ('city','month','valueCents','beneficiaries')} for d in docs for r in d['records']]
    evidence=[{k:v for k,v in d.items() if k!='records'} for d in docs]
    release=hashlib.sha256(json.dumps(evidence,sort_keys=True).encode()).hexdigest()[:16]
    snapshot={'schemaVersion':1,'program':'Novo Bolsa Família','release':release,'updatedAt':datetime.now(timezone.utc).isoformat(),'source':'https://portaldatransparencia.gov.br/download-de-dados/novo-bolsa-familia','geographyBasis':'SIAFI identifiers from complete monthly official files; catalog is union of observed municipalities','quantityMethod':docs[0]['beneficiaryMethod'],'requestedMonths':periods,'cities':list(catalog.values()),'coverage':{d['month']:{'receivedCities':d['municipalities'],'expectedCities':len(catalog),'sourceFileComplete':True} for d in docs},'records':rows}
    out=Path(output);out.mkdir(parents=True,exist_ok=True)
    (out/'snapshot.json').write_text(json.dumps(snapshot,ensure_ascii=False,separators=(',',':'))+'\n')
    save(out/'source-manifest.json',{'release':release,'monthlyFiles':evidence,'sourceRows':sum(d['sourceRows'] for d in docs),'valueCents':sum(d['valueCents'] for d in docs),'snapshotSha256':sha(out/'snapshot.json')})
    print(json.dumps({'release':release,'months':len(docs),'municipalities':len(catalog),'sourceRows':sum(d['sourceRows'] for d in docs)}),flush=True)


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--start',required=True);p.add_argument('--end',required=True)
    p.add_argument('--root',default='work/bulk');p.add_argument('--output',default='work/history')
    p.add_argument('--workers',type=int,choices=[1,2],default=1)
    p.add_argument('--no-annual-details',action='store_true')
    p.add_argument('--keep-month',action='append',default=[])
    args=p.parse_args();root=Path(args.root).resolve();root.mkdir(parents=True,exist_ok=True)
    periods=list(months(args.start,args.end))
    years=sorted({m[:4] for m in periods})
    def year(y):
        for m in periods:
            if m.startswith(y):process_month(m,root,not args.no_annual_details,m in args.keep_month)
    with concurrent.futures.ThreadPoolExecutor(max_workers=args.workers) as pool:list(pool.map(year,years))
    history(root,periods,args.output)


if __name__=='__main__':main()
