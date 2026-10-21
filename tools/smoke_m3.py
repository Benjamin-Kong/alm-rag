"""M3 runtime-only offline smoke: local tokenizer + mock model + temporary SQLite.

Execute backend image stdin with --network none. No pytest/dev dependencies,
real model weights, ALM servers, active revisions or index publication.
"""
import hashlib
import json
from pathlib import Path
from tempfile import TemporaryDirectory

import httpx
from tokenizers import Tokenizer,models,pre_tokenizers,processors

from almrag.config import Settings
from almrag.embedding import LocalTokenizer,ModelConfig,OllamaEmbedder
from almrag.processing import ProcessingService,ProcessingPolicy,FieldRef
from almrag.queue import Queue
from almrag.storage import Database,canonical_uid
from almrag.worker import run_once


def main():
    with TemporaryDirectory(prefix='almrag-m3-offline-') as directory:
        root=Path(directory)
        db=Database(root/'fixture.sqlite');db.migrate();db.migrate()
        instance=db.add_instance('codebeamer','https://source.example.invalid','Synthetic','env:SYNTHETIC')
        project=db.add_project(instance,'p','Synthetic')
        tokenizer=Tokenizer(models.WordLevel({'[UNK]':0,'word':1,'[BOS]':2,'[PAD]':3},unk_token='[UNK]'))
        tokenizer.pre_tokenizer=pre_tokenizers.Whitespace()
        tokenizer.post_processor=processors.TemplateProcessing(single='[BOS] $A',special_tokens=[('[BOS]',2)])
        tokenizer.enable_truncation(max_length=8);tokenizer.enable_padding(length=32,pad_id=3,pad_token='[PAD]')
        path=root/'tokenizer.json';tokenizer.save(str(path));checksum=hashlib.sha256(path.read_bytes()).hexdigest()
        exact=LocalTokenizer(path,checksum)
        tokenizer.no_truncation();tokenizer.no_padding()  # Independent complete-input reference.
        assert exact.count('word '*15000)==15001
        model=ModelConfig(expected_digest='sha256:'+'e'*64,vector_dimension=3)
        calls=[]
        def handler(request):
            body=json.loads(request.content) if request.content else None
            calls.append((request.url.path,body))
            if request.url.path=='/api/tags':return httpx.Response(200,json={'models':[{'name':model.model_name+':latest','digest':model.expected_digest}]})
            if request.url.path=='/api/show':return httpx.Response(200,json={'capabilities':['embedding'],'model_info':{'fixture.context_length':1024}})
            assert request.url.path=='/api/embed' and body['truncate'] is False
            count=len(tokenizer.encode(body['input'],add_special_tokens=True).ids)
            assert count<=1024
            return httpx.Response(200,json={'model':model.model_name,'embeddings':[[1.0,2.0,3.0]],'prompt_eval_count':count})
        runtime=OllamaEmbedder('https://model.example.invalid',model,exact,transport=httpx.MockTransport(handler),allow_fixture=True)
        service=ProcessingService(db,lambda _:runtime,allow_fixture=True)
        service.configure(project,ProcessingPolicy(fields=[FieldRef(kind='NORMALIZED',key='description')]))
        item=canonical_uid('item',project,'1');revision=canonical_uid('revision',item,'1')
        table='<table><tr><th>Key</th><th>Value</th></tr>'+''.join('<tr><td>row'+str(n)+'</td><td>word value'+str(n)+'</td></tr>' for n in range(100))+'</table>'
        source='<p>'+'word '*15000+'</p>'+table
        envelope={'id':'1','project_id':'p','scope_id':'t','revision':'1','title':'Synthetic','description':{'format':'text/html','raw':source},'fields':[],'raw':{'unselected':'retained','description':source}}
        with db.transaction() as c:
            c.execute("INSERT INTO jobs(job_id,project_uid,stage,state,created_at,updated_at) VALUES('collect',?,'COLLECT','SUCCEEDED',0,0)",(project,))
            c.execute('INSERT INTO items(item_uid,project_uid,source_item_id) VALUES(?,?,?)',(item,project,'1'))
            c.execute('INSERT INTO item_revisions(revision_uid,item_uid,source_revision,raw_payload,hash) VALUES(?,?,?,?,?)',(revision,item,'1',json.dumps(envelope),hashlib.sha256(source.encode()).hexdigest()))
            c.execute("INSERT INTO item_collection_state VALUES(?,?,'collect')",(item,revision))
            c.execute("INSERT INTO collection_memberships VALUES(?,?,'t','IN_SCOPE','collect')",(project,'1'))
        def execute(stage):
            queued=service.enqueue(project,stage)
            assert run_once(Queue(db),'offline',processing_service=service)
            assert Queue(db).get_job(queued['job_id'])['state']=='SUCCEEDED'
        execute('PROCESS');execute('EMBED')
        content_calls=sum(path=='/api/embed' for path,_ in calls)
        execute('PROCESS');execute('EMBED')
        assert sum(path=='/api/embed' for path,_ in calls)==content_calls
        assert runtime.profile['state']=='FIXTURE_ONLY'
        assert hashlib.sha256(path.read_bytes()).hexdigest()==checksum
        with db.connect() as c:
            chunks=c.execute('SELECT input_text,input_tokens FROM chunks').fetchall()
            assert len(chunks)>20
            assert all(row['input_tokens']==len(tokenizer.encode(row['input_text'],add_special_tokens=True).ids)<=1024 for row in chunks)
            assert json.loads(c.execute('SELECT raw_payload FROM item_revisions').fetchone()[0])==envelope
            structured=json.loads(c.execute("SELECT table_json FROM content_blocks WHERE type='table'").fetchone()[0])
            assert len(structured['grid'])==101
            assert c.execute('SELECT count(*) FROM embedding_chunk_vectors').fetchone()[0]==len(chunks)
            assert c.execute('SELECT state FROM processing_results').fetchone()[0]=='EMBED_READY'
            assert c.execute('SELECT active_revision_uid FROM items').fetchone()[0] is None
            assert c.execute('SELECT count(*) FROM index_generations').fetchone()[0]==0
            assert [row[0] for row in c.execute('SELECT version FROM schema_migrations ORDER BY version')]==[1,2,3,4,5,6,7,8,9]
        assert not Settings().live_alm_enabled and not Settings().live_model_enabled
        print('M3_OFFLINE_RUNTIME_PASS',len(chunks),'chunks',content_calls-2,'content embedding requests; repeat=0; FIXTURE_ONLY')


if __name__=='__main__':main()
