"""SRS-011/013/014/015/016/048/049/055: real API/worker/storage, mock HTTP."""
import json
import re

import httpx
import pytest
from fastapi.testclient import TestClient

from almrag.api import create_app
from almrag.collection import CollectionService
from almrag.config import Settings
from almrag.connection import Connections
from almrag.embedding import ModelConfig, OllamaEmbedder
from almrag.processing import ProcessingService
from almrag.queue import Queue
from almrag.storage import Database
from almrag.worker import run_once
from test_m2_api import register, project


class ExactSyntheticTokenizer:
    """Named fixture contract: each Unicode codepoint is one synthetic token."""
    identity = 'fixture:mock-e2e-codepoints-v1'

    def count(self, text):
        return len(text)


@pytest.fixture
def pipeline(tmp_path):
    db = Database(tmp_path/'m3.sqlite')
    db.migrate()
    source_items = {}
    alm_calls, model_calls = [], []
    digest = 'sha256:'+'c'*64
    model = ModelConfig(expected_digest=digest,vector_dimension=2)
    tokenizer = ExactSyntheticTokenizer()

    def source_http(request):
        alm_calls.append(request)
        path = request.url.path
        if path == '/v3/projects':
            return httpx.Response(200,json=[{'id':1,'name':'Project'}])
        if path == '/v3/projects/1/trackers':
            return httpx.Response(200,json=[{'id':31,'name':'Requirements'}])
        if path == '/v3/trackers/31/fields':
            return httpx.Response(200,json=[{'id':3,'name':'Name'},{'id':80,'name':'Description'}])
        if path == '/v3/trackers/31/items':
            return httpx.Response(200,json=[{'id':item,'version':1} for item in source_items])
        match = re.fullmatch('/v3/items/([0-9]+)(/relations|/attachments)?',path)
        if match:
            item, suffix = match.groups()
            if suffix == '/relations':
                return httpx.Response(200,json={})
            if suffix == '/attachments':
                return httpx.Response(200,json=[])
            return httpx.Response(200,json={'id':int(item),'tracker':{'id':31},'version':1,
                'name':'Synthetic '+item,'description':source_items[int(item)],'descriptionFormat':'HTML',
                'customFields':[{'fieldId':999,'type':'JSON','value':{'opaque':['complete','unselected']}}]})
        raise AssertionError((request.method,path))

    def model_http(request):
        payload = json.loads(request.content) if request.content else None
        model_calls.append((request.method,request.url.path,payload))
        if request.url.path == '/api/tags':
            return httpx.Response(200,json={'models':[{'name':model.model_name+':latest','digest':digest}]})
        if request.url.path == '/api/show':
            return httpx.Response(200,json={'capabilities':['embedding'],'model_info':{'fixture.context_length':1024}})
        if request.url.path == '/api/embed':
            assert payload['truncate'] is False
            assert payload['dimensions'] == 2
            assert payload['options']['num_ctx'] == 1024
            return httpx.Response(200,json={'model':model.model_name,'embeddings':[[1.0,2.0]],
                                           'prompt_eval_count':tokenizer.count(payload['input'])})
        raise AssertionError((request.method,request.url.path))

    settings = Settings(allowed_origin='https://testserver')
    connections = Connections(db,settings,transport_factory=lambda _:httpx.MockTransport(source_http),
                              secret_resolver=lambda _:'synthetic-secret')
    collection = CollectionService(db,connections.connector,tmp_path/'attachments')
    runtime = OllamaEmbedder('http://127.0.0.1:11434',model,tokenizer,
                            transport=httpx.MockTransport(model_http),allow_fixture=True)
    processing = ProcessingService(db,lambda _:runtime,allow_fixture=True)
    app = create_app(settings,db=db,connections=connections,collection=collection,processing=processing)
    app.state.security.bootstrap('admin','long synthetic password')
    with TestClient(app,base_url='https://testserver') as client:
        response = client.post('/api/v1/auth/login',json={'username':'admin','password':'long synthetic password'},
                               headers={'Origin':'https://testserver'})
        assert response.status_code == 204
        headers = {'Origin':'https://testserver','X-CSRF-Token':client.cookies['almrag_csrf']}
        env = app,client,headers,db,alm_calls
        project_uid = project(env,register(env))
        result = {'app':app,'client':client,'headers':headers,'db':db,'project':project_uid,
                  'items':source_items,'alm_calls':alm_calls,'model_calls':model_calls,'runtime':runtime}
        yield result


def execute(pipeline,stage,expected='SUCCEEDED'):
    p = pipeline
    response = p['client'].post(f"/api/v1/projects/{p['project']}/jobs",headers=p['headers'],json={'stage':stage})
    assert response.status_code == 202,response.text
    assert run_once(Queue(p['db']),'mock-e2e',p['app'].state.collection,
                    processing_service=p['app'].state.processing,lease_seconds=60)
    job = p['client'].get('/api/v1/jobs/'+response.json()['job_id']).json()
    assert job['state'] == expected,job
    return job


def selected_description(p):
    response = p['client'].put(f"/api/v1/projects/{p['project']}/processing-config",headers=p['headers'],
                              json={'fields':[{'kind':'NORMALIZED','key':'description'}]})
    assert response.status_code == 200,response.text


def content_inputs(p):
    return [payload['input'] for _,path,payload in p['model_calls']
            if path == '/api/embed' and payload['input'].startswith('Title:')]


def complete_spans(source,spans):
    covered = 0
    for span in sorted(spans,key=lambda value:(value['char_start'],value['char_end'])):
        assert span['char_start'] <= covered
        assert 0 <= span['char_start'] <= span['char_end'] <= len(source)
        assert span['utf8_byte_start'] == len(source[:span['char_start']].encode())
        assert span['utf8_byte_end'] == len(source[:span['char_end']].encode())
        covered = max(covered,span['char_end'])
    assert covered == len(source)


def test_api_worker_merged_table_large_item_and_unchanged_embedding_reuse(pipeline):
    """SRS-011/013/014/015/016/049: complete bounded content through every layer."""
    p = pipeline
    paragraph = 'あ'*15000  # Exactly 15,000 synthetic fixture tokens before input context.
    large_cell = '긴셀'*4000
    table = ('<table><tr><th colspan="2">Details</th></tr><tr><th>Key</th><th>Value</th></tr>'
             '<tr><td rowspan="2">shared</td><td>'+large_cell+'</td></tr>'
             '<tr><td>last value</td></tr>' +
             ''.join(f'<tr><td>key {row}</td><td>value {row}</td></tr>' for row in range(98)) +
             '</table>')
    raw = '<p>'+paragraph+'</p>'+table
    p['items'][100] = raw
    selected_description(p)
    execute(p,'COLLECT')
    before_processing_alm_calls = len(p['alm_calls'])
    pre = p['client'].post(f"/api/v1/projects/{p['project']}/processing-preflight",headers=p['headers']).json()
    assert pre['process_ready'] and not pre['embed_ready'] and not pre['sync_ready'],pre
    assert p['runtime'].profile['state'] == 'FIXTURE_ONLY'
    calibration = [payload for _,path,payload in p['model_calls'] if path == '/api/embed']
    assert len(calibration) == 2
    execute(p,'PROCESS')
    execute(p,'EMBED')
    inputs = content_inputs(p)
    assert inputs and all(len(value) <= 1024 for value in inputs)
    assert any('Details / Value' in value and 'Row r2' in value for value in inputs)
    with p['db'].connect() as sql:
        envelope = json.loads(sql.execute('SELECT raw_payload FROM item_revisions').fetchone()[0])
        assert envelope['raw']['description'] == raw
        assert envelope['raw']['customFields'][0]['value'] == {'opaque':['complete','unselected']}
        blocks = sql.execute('SELECT * FROM content_blocks ORDER BY block_order').fetchall()
        assert len(blocks) == 2 and blocks[0]['normalized_text'] == paragraph
        table_json = json.loads(blocks[1]['table_json'])
        assert len(table_json['grid']) - len(table_json['header_rows']) == 100
        assert table_json['cells'][0]['colspan'] == 2
        assert any(cell['rowspan'] == 2 for cell in table_json['cells'])
        assert any(cell['text'] == large_cell for cell in table_json['cells'])
        for block in blocks:
            chunk_rows = sql.execute('SELECT * FROM chunks WHERE block_uid=?',(block['block_uid'],)).fetchall()
            assert all(row['input_tokens'] == len(row['input_text']) <= row['effective_max_input_tokens'] for row in chunk_rows)
            spans = [span for row in chunk_rows for span in json.loads(row['source_span_offsets'])]
            if block['type'] == 'text':
                complete_spans(paragraph,spans)
            else:
                for cell in table_json['cells']:
                    complete_spans(cell['text'],[span for span in spans if span.get('cell_id') == cell['cell_id']])
        assert sql.execute("SELECT state FROM processing_results").fetchone()[0] == 'EMBED_READY'
        manifest = sql.execute('SELECT chunk_count FROM embedding_manifests').fetchone()[0]
        assert manifest > 20
        assert manifest == sql.execute('SELECT count(*) FROM chunks').fetchone()[0]
        assert manifest == sql.execute('SELECT count(*) FROM embedding_chunk_vectors').fetchone()[0]
        assert sql.execute('SELECT active_revision_uid FROM items').fetchone()[0] is None
        assert sql.execute('SELECT count(*) FROM index_generations').fetchone()[0] == 0
    embed_requests = sum(path == '/api/embed' for _,path,_ in p['model_calls'])
    execute(p,'PROCESS')
    execute(p,'EMBED')
    assert content_inputs(p) == inputs
    assert sum(path == '/api/embed' for _,path,_ in p['model_calls']) == embed_requests
    assert len(p['alm_calls']) == before_processing_alm_calls
    assert all(request.method == 'GET' for request in p['alm_calls'])


def test_api_worker_normalizer_item_failure_preserves_raw_and_continues_sibling(pipeline):
    """SRS-011/055: malformed table is visible locally and cannot discard siblings."""
    p = pipeline
    invalid = '<table><tr><th>Header</th></tr><tr><td><table><tr><th>Nested</th></tr></table></td></tr></table>'
    p['items'].update({100:invalid,101:'<p>Valid sibling survives.</p>'})
    selected_description(p)
    execute(p,'COLLECT')
    job = execute(p,'PROCESS',expected='COMPLETED_WITH_ERRORS')
    durable = Queue(p['db']).get_job(job['job_id'])
    assert (durable['progress_total'],durable['succeeded_items'],durable['failed_items']) == (2,1,1)
    assert content_inputs(p) == []
    with p['db'].connect() as sql:
        failed = sql.execute('SELECT * FROM failed_items').fetchone()
        assert failed['error_class'] == 'TABLE_NESTED_UNSUPPORTED' and failed['failed_stage'] == 'PROCESS'
        raw = json.loads(sql.execute('SELECT raw_payload FROM item_revisions WHERE revision_uid=?',(failed['revision_uid'],)).fetchone()[0])
        assert raw['raw']['description'] == invalid
        assert sql.execute('SELECT count(*) FROM processing_results').fetchone()[0] == 1
        assert sql.execute('SELECT count(*) FROM chunks').fetchone()[0] == 1
        assert sql.execute("SELECT count(*) FROM items WHERE active_revision_uid IS NOT NULL").fetchone()[0] == 0
        assert sql.execute('SELECT count(*) FROM index_generations').fetchone()[0] == 0


def test_api_worker_local_tokenizer_artifact_ignores_saved_truncation_and_padding(pipeline,tmp_path):
    """SRS-013/014/049: real local artifact counts complete input through mock HTTP.

    This is an integration regression for the already-fixed OI-047. Independent
    WordLevel reference counts supply mock Ollama's prompt_eval_count; no deployed
    model/tokenizer compatibility or production calibration is asserted.
    """
    import hashlib
    from tokenizers import Tokenizer, models, pre_tokenizers
    from almrag.embedding import LocalTokenizer

    p = pipeline
    vocabulary = {'[UNK]':0,'[PAD]':1,'alpha':2,'beta':3}
    stored = Tokenizer(models.WordLevel(vocabulary,unk_token='[UNK]'))
    stored.pre_tokenizer = pre_tokenizers.WhitespaceSplit()
    stored.enable_truncation(max_length=2)
    stored.enable_padding(length=64,pad_id=1,pad_token='[PAD]')
    artifact = tmp_path/'synthetic-tokenizer.json'
    artifact.write_text(stored.to_str())
    local = LocalTokenizer(artifact,hashlib.sha256(artifact.read_bytes()).hexdigest())
    reference = Tokenizer(models.WordLevel(vocabulary,unk_token='[UNK]'))
    reference.pre_tokenizer = pre_tokenizers.WhitespaceSplit()
    assert len(stored.encode('alpha '*200).ids) == 64
    assert local.count('alpha '*200) == len(reference.encode('alpha '*200).ids) == 200
    assert local.count('alpha') == 1
    model = ModelConfig(expected_digest='sha256:'+'d'*64,vector_dimension=2,effective_max_input_tokens=128)
    calls = []

    def model_http(request):
        body = json.loads(request.content) if request.content else None
        calls.append((request.url.path,body))
        if request.url.path == '/api/tags':
            return httpx.Response(200,json={'models':[{'name':model.model_name+':latest','digest':model.expected_digest}]})
        if request.url.path == '/api/show':
            return httpx.Response(200,json={'capabilities':['embedding'],'model_info':{'fixture.context_length':128}})
        assert request.url.path == '/api/embed'
        count = len(reference.encode(body['input'],add_special_tokens=True).ids)
        assert body['truncate'] is False and body['options']['num_ctx'] == 128
        assert count <= 128
        return httpx.Response(200,json={'model':model.model_name,'embeddings':[[1.0,2.0]],'prompt_eval_count':count})

    runtime = OllamaEmbedder('http://127.0.0.1:11434',model,local,
                            transport=httpx.MockTransport(model_http),allow_fixture=True)
    p['app'].state.processing = ProcessingService(p['db'],lambda _:runtime,allow_fixture=True)
    p['items'][100] = '<p>'+'alpha beta '*1000+'</p>'
    selected_description(p)
    execute(p,'COLLECT')
    execute(p,'PROCESS')
    execute(p,'EMBED')
    assert runtime.profile['state'] == 'FIXTURE_ONLY'
    assert runtime.profile['tokenizer_id'] == local.identity
    with p['db'].connect() as sql:
        chunks = sql.execute('SELECT * FROM chunks').fetchall()
        assert len(chunks) > 10
        for chunk in chunks:
            expected = len(reference.encode(chunk['input_text'],add_special_tokens=True).ids)
            assert chunk['input_tokens'] == expected <= chunk['effective_max_input_tokens'] == 128
            assert chunk['tokenizer_id'] == local.identity
        assert sql.execute('SELECT state FROM processing_results').fetchone()[0] == 'EMBED_READY'
        assert sql.execute('SELECT count(*) FROM embedding_chunk_vectors').fetchone()[0] == len(chunks)
    before = sum(path == '/api/embed' for path,_ in calls)
    assert before >= 3  # Two calibration requests plus at least one distinct content input.
    execute(p,'PROCESS')
    execute(p,'EMBED')
    assert sum(path == '/api/embed' for path,_ in calls) == before


def test_api_worker_100_items_three_parser_failures_keep_97_successes(pipeline):
    """SRS-011/049/055: real bulk PROCESS preserves failures and all source Items."""
    p = pipeline
    invalid = '<table><tr><th>Header</th></tr><tr><td><table><tr><th>Nested</th></tr></table></td></tr></table>'
    rejected = {102,144,178}
    for item in range(100,200):
        p['items'][item] = invalid if item in rejected else f'<p>Valid item {item}.</p>'
    selected_description(p)
    execute(p,'COLLECT')
    job = execute(p,'PROCESS',expected='COMPLETED_WITH_ERRORS')
    durable = Queue(p['db']).get_job(job['job_id'])
    assert (durable['progress_total'],durable['succeeded_items'],durable['failed_items'],durable['skipped_items']) == (100,97,3,0)
    assert content_inputs(p) == []
    with p['db'].connect() as sql:
        assert sql.execute('SELECT count(*) FROM items').fetchone()[0] == 100
        originals = [json.loads(row[0]) for row in sql.execute('SELECT raw_payload FROM item_revisions')]
        assert len(originals) == 100
        assert {int(value['id']):value['raw']['description'] for value in originals} == p['items']
        failures = sql.execute('SELECT f.*,i.source_item_id FROM failed_items f JOIN items i USING(item_uid)').fetchall()
        assert {int(value['source_item_id']) for value in failures} == rejected
        assert all(value['error_class'] == 'TABLE_NESTED_UNSUPPORTED' and value['failed_stage'] == 'PROCESS' for value in failures)
        assert sql.execute("SELECT count(*) FROM processing_results WHERE state='PROCESS_READY'").fetchone()[0] == 97
        assert sql.execute('SELECT count(*) FROM chunks').fetchone()[0] == 97
        assert sql.execute('SELECT count(*) FROM processing_outcomes WHERE job_id=?',(job['job_id'],)).fetchone()[0] == 100
        assert sql.execute('SELECT count(*) FROM embedding_cache').fetchone()[0] == 0
        assert sql.execute('SELECT count(*) FROM embedding_manifests').fetchone()[0] == 0
        assert sql.execute('SELECT count(*) FROM items WHERE active_revision_uid IS NOT NULL').fetchone()[0] == 0
        assert sql.execute('SELECT count(*) FROM index_generations').fetchone()[0] == 0
    preflight = p['client'].post(f"/api/v1/projects/{p['project']}/processing-preflight",headers=p['headers']).json()
    assert preflight['process_ready'] and not preflight['embed_ready']
    assert 'PROCESS_REQUIRED' in preflight['diagnostics']
