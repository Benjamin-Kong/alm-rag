"""SRS-035/036 synthetic capacity/search prototype, isolated temporary DB only.

This seeds canonical published fixture rows directly; it does not measure source
collection, processing or model embedding throughput. Network requires explicit
loopback synthetic Qdrant opt-in. Only the random collection this run owns is
removed. No application/customer database path can be supplied.
"""
import argparse
import json
import math
import os
from pathlib import Path
import platform
import tempfile
import time
from uuid import uuid4

from almrag.embedding import ModelConfig,fingerprint
from almrag.lexical import LEXICAL_VERSION,terms,_encoded
from almrag.retrieval import SearchService,SearchRequest
from almrag.storage import Database,canonical_uid
from almrag.vector_store import VectorStore


def nearest_rank(values,quantile=.95):
    if not values or not 0<quantile<=1 or any(isinstance(v,bool) or not isinstance(v,(int,float)) or not math.isfinite(v) or v<0 for v in values):raise ValueError('Finite nonempty latency samples required')
    return sorted(values)[math.ceil(len(values)*quantile)-1]


class FixtureTokenizer:
    identity='fixture:benchmark-codepoints-v1'
    def count(self,text):return len(text)


class FixtureRuntime:
    def __init__(self):
        self.tokenizer=FixtureTokenizer()
        self.config=ModelConfig(expected_digest='sha256:'+'a'*64,vector_dimension=2)
        self.profile={'state':'FIXTURE_ONLY','tokenizer_id':self.tokenizer.identity,'config':self.config.model_dump(),'model_digest':self.config.expected_digest,'calibration_evidence':['synthetic benchmark; not model calibration']}
        self.profile['fingerprint']=fingerprint(self.profile)
    def embed(self,text,*,expected_tokens):return [1.,0.]


def _seed(db,store,collection,item_count,runtime):
    instance=db.add_instance('codebeamer','https://synthetic.invalid','Synthetic capacity','ENV:SYNTHETIC_NOT_RESOLVED')
    project=db.add_project(instance,'synthetic-capacity','Synthetic capacity')
    generation=str(uuid4());batch=[];distribution={}
    store.ensure_collection(collection,2)
    with db.transaction() as c:
        c.execute("INSERT INTO project_selections(project_uid,selection_mode,scope_kind,scope_ids,config_revision) VALUES(?,'ALL','TRACKER','[]',1)",(project,))
        c.execute("INSERT INTO jobs(job_id,project_uid,stage,state,created_at,updated_at) VALUES('synthetic',?,'COLLECT','SUCCEEDED',0,0)",(project,))
        c.execute("INSERT INTO index_generations VALUES(?,?,?,'VALIDATED','synthetic fixture seeded',NULL)",(generation,project,json.dumps(runtime.profile)))
        c.execute('INSERT INTO generation_configs VALUES(?,?,?,?,?,?,?,?)',(generation,'synthetic',json.dumps(runtime.profile),'{}',LEXICAL_VERSION,collection,'ACTIVE','[]'))
        for number in range(item_count):
            source=f'SYN-{number:06d}';item=canonical_uid('item',project,source);revision=canonical_uid('revision',item,'1');result=canonical_uid('result',revision)
            envelope={'id':source,'project_id':'synthetic-capacity','scope_id':'synthetic-tracker','revision':'1','title':f'Synthetic {source}','description':{'format':'text/plain','raw':'synthetic capacity fixture'},'fields':[],'attachments':[],'relations':[]}
            c.execute('INSERT INTO items(item_uid,project_uid,source_item_id) VALUES(?,?,?)',(item,project,source))
            c.execute('INSERT INTO item_revisions(revision_uid,item_uid,source_revision,raw_payload,hash) VALUES(?,?,?,?,?)',(revision,item,'1',json.dumps(envelope),fingerprint({'envelope':envelope,'attachment_checksums':[]})))
            c.execute("INSERT INTO item_collection_state VALUES(?,?,'synthetic')",(item,revision))
            c.execute("INSERT INTO collection_memberships VALUES(?,?,?,'IN_SCOPE','synthetic')",(project,source,'synthetic-tracker'))
            c.execute("INSERT INTO processing_results VALUES(?,?,?,?,?,?,'EMBED_READY','{}')",(result,project,item,revision,'synthetic',runtime.profile['fingerprint']))
            points=[];chunk_count=1+number%3;distribution[chunk_count]=distribution.get(chunk_count,0)+1
            for ordinal in range(chunk_count):
                text=f'Synthetic {source} section {ordinal}';chunk=canonical_uid('chunk',revision,str(ordinal));digest=fingerprint(text);pid=canonical_uid('point',generation,chunk)
                c.execute('INSERT INTO chunks(chunk_uid,revision_uid,chunk_key,input_text,content_hash,model_fingerprint,input_tokens,source_span_offsets,row_ids,embedding_input_digest,tokenizer_id,effective_max_input_tokens) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)',(chunk,revision,str(ordinal),text,digest,runtime.profile['fingerprint'],len(text),'[]','[]',digest,runtime.tokenizer.identity,8192))
                c.execute('INSERT INTO processing_membership VALUES(?,?)',(result,chunk))
                payload=dict(project_uid=project,generation_uid=generation,item_uid=item,revision_uid=revision,chunk_uid=chunk,result_uid=result,content_hash=digest,model_fingerprint=runtime.profile['fingerprint'],vector_digest=fingerprint([1.,0.]))
                point={'id':pid,'vector':[1.,0.],'payload':payload}
                c.execute("INSERT INTO index_points VALUES(?,?,?,'READY',?)",(pid,generation,chunk,digest))
                document_terms=' '.join(_encoded(terms(text+' '+item+' '+source)))
                # All fixture UUIDs are new: no UNINDEXED FTS delete scan is needed.
                c.execute('INSERT INTO keyword_documents VALUES(?,?,?,?,?,?,?)',(pid,project,generation,item,revision,chunk,document_terms))
                c.execute('INSERT INTO keyword_fts(point_uuid,project_uid,generation_uid,terms) VALUES(?,?,?,?)',(pid,project,generation,document_terms))
                points.append(point);batch.append(point)
                if len(batch)==1000:store.upsert(collection,batch);batch=[]
            c.execute('INSERT INTO index_publications VALUES(?,?,?,?,?,?,?,?)',(generation,item,result,revision,fingerprint(points),len(points),json.dumps(points),'synthetic fixture'))
            c.execute('UPDATE items SET active_revision_uid=? WHERE item_uid=?',(revision,item))
        if batch:store.upsert(collection,batch)
        c.execute('UPDATE projects SET active_generation_uid=? WHERE project_uid=?',(generation,project))
    return project,generation,distribution


def run_benchmark(store,*,item_count=100000,samples=100,warmups=5):
    for value,minimum,maximum in ((item_count,10,1000000),(samples,1,10000),(warmups,0,1000)):
        if type(value) is not int or not minimum<=value<=maximum:raise ValueError('Invalid benchmark bounds')
    collection='almrag_'+uuid4().hex
    with tempfile.TemporaryDirectory(prefix='almrag-m6-benchmark-') as folder:
        db=Database(Path(folder)/'synthetic.sqlite');db.migrate();runtime=FixtureRuntime()
        try:
            started=time.perf_counter();project,generation,distribution=_seed(db,store,collection,item_count,runtime);seed_seconds=time.perf_counter()-started
            service=SearchService(db,lambda _:runtime,store,allow_fixture=True)
            latencies=[];returned=[];exact=0
            for index in range(warmups+samples):
                # Exact-ID query tests the production priority channel as well as both retrieval backends.
                query=f'SYN-{(index*7919)%item_count:06d}'
                request=SearchRequest(query=query,project_uids=[project],top_k=10)
                started=time.perf_counter();response=service.search(request,allowed_projects=[project]);elapsed=time.perf_counter()-started
                if index>=warmups:
                    latencies.append(elapsed);returned.append(response['total'])
                    exact+=bool(response['results'] and response['results'][0]['item_uid']==canonical_uid('item',project,query))
            with db.connect() as c:
                counts={name:c.execute('SELECT count(*) FROM '+name).fetchone()[0] for name in ('items','item_revisions','chunks','index_points','keyword_documents','index_publications')}
                integrity=c.execute('PRAGMA integrity_check').fetchone()[0]
                foreign_keys=len(c.execute('PRAGMA foreign_key_check').fetchall())
                c.execute('PRAGMA wal_checkpoint(TRUNCATE)')
            qdrant_count=store._request('POST','/collections/'+collection+'/points/count',{'exact':True})['count']
            return dict(status_scope='SYNTHETIC_CAPACITY_AND_RETRIEVAL_FUNCTIONALITY',production_pipeline={'status':'NOT VERIFIED','reason':'Direct retrieval-shape fixture has no real normalization blocks, processor policy or embedding manifest; distribution1/2/3 is generated, not an ALM estimate'},status='PASS' if qdrant_count==counts['chunks'] and integrity=='ok' and foreign_keys==0 and all(n==10 for n in returned) and exact==samples else 'FAIL',fixture_seeding=dict(seconds=seed_seconds,is_collector_embedding_throughput=False,description='Direct canonical published fixture seeding; deterministic two-dimensional fixture embeddings'),capacity=dict(items=counts['items'],chunks=counts['chunks'],average_chunks_per_item=counts['chunks']/counts['items'],chunk_count_distribution={str(k):v for k,v in distribution.items()},sqlite_bytes=db.path.stat().st_size,qdrant_points=qdrant_count,table_counts=counts,sqlite_integrity=integrity,foreign_key_violations=foreign_keys),search=dict(mode='hybrid',query_distribution='exact source ID, deterministic stride 7919',samples=samples,warmups=warmups,top_k=10,concurrency=1,response='compact',returned_items=returned,exact_id_rank_one=exact,p50_seconds=nearest_rank(latencies,.5),p95_seconds=nearest_rank(latencies,.95),max_seconds=max(latencies),raw_seconds=latencies,synthetic_p95_under_3_seconds=nearest_rank(latencies,.95)<=3,latency_status='PASS' if nearest_rank(latencies,.95)<=3 else 'FAIL'),actual_ollama_target={'status':'NOT VERIFIED','reason':'No real Ollama/model/tokenizer; synthetic local storage/search timing only'},embedding_environments={key:'NOT VERIFIED' for key in ('CPU','GPU','REMOTE')},hardware=dict(platform=platform.platform(),machine=platform.machine(),processor=platform.processor(),logical_cpus=os.cpu_count()),cleanup='Random owned Qdrant collection and temporary SQLite removed in finally')
        finally:store.delete_collection(collection)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--synthetic-loopback-qdrant',action='store_true',required=True)
    parser.add_argument('--items',type=int,default=100000);parser.add_argument('--samples',type=int,default=100);parser.add_argument('--warmups',type=int,default=5)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    store=VectorStore('http://127.0.0.1:16333',auth_headers={'api-key':'synthetic-m4-only'},allow_live=True,timeout_seconds=120)
    report=run_benchmark(store,item_count=args.items,samples=args.samples,warmups=args.warmups)
    args.output.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({'status':report['status'],'items':report['capacity']['items'],'chunks':report['capacity']['chunks'],'p95_seconds':report['search']['p95_seconds']}))
    return 0 if report['status']=='PASS' else 1


if __name__=='__main__':raise SystemExit(main())
