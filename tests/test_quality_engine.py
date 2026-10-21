"""SRS-033/034: durable bounded quality jobs and actual retrieval comparisons."""
import json
from almrag.embedding import fingerprint
import pytest
from almrag.quality import QualityService,QualityError,metrics
from almrag.queue import Queue,LeaseLost
from almrag.retrieval import SearchRequest
from test_processing import setup,add_item,execute
from test_retrieval import publish,service


def prepared(setup):
    db,_,p,r,_=setup
    rev=add_item(setup);execute(setup);execute(setup,'EMBED');search,dense=service(setup);generation=publish(setup,dense)
    with db.connect() as c:item=c.execute('SELECT item_uid FROM items').fetchone()[0]
    with db.transaction() as c:
        c.execute('DROP TRIGGER immutable_revision_update')
        for row in c.execute('SELECT revision_uid,raw_payload FROM item_revisions').fetchall():c.execute('UPDATE item_revisions SET hash=? WHERE revision_uid=?',(fingerprint({'envelope':json.loads(row['raw_payload']),'attachment_checksums':[]}),row['revision_uid']))
        for pub in c.execute('SELECT * FROM index_publications').fetchall():
            docs=[dict(r) for r in c.execute('SELECT * FROM keyword_documents WHERE generation_uid=? ORDER BY point_uuid',(generation,))]
            c.execute('UPDATE index_publications SET lexical_digest=? WHERE generation_uid=? AND item_uid=?',(fingerprint(docs),generation,pub['item_uid']))
    dense.retrieve=lambda collection,ids:[dense.points[i] for i in ids if i in dense.points]
    return QualityService(db,search,dense),search,dense,item,generation


def finish(q,job):
    claimed=q.queue.claim('quality-test',300);assert claimed['job_id']==job['job_id']
    q.run(claimed,lambda:False)
    return q.report(job['job_id'])


def test_metrics_unique_items_k_denominator():
    assert metrics(['a','a','b'],['b'],3)=={'precision_at_k':1/3,'recall_at_k':1.0,'mrr':.5}
    assert metrics([],['b'],10)=={'precision_at_k':0.,'recall_at_k':0.,'mrr':0.}


def test_keyword_avoids_runtime_and_dense_dense_avoids_lexical(setup):
    q,s,d,item,g=prepared(setup)
    s.runtime_factory=lambda _:pytest.fail('keyword invoked model')
    assert s.search(SearchRequest(query='Title',project_uids=[setup[2]]),allowed_projects=[setup[2]],method='keyword')['total']==1
    assert not d.calls
    s.runtime_factory=lambda _:setup[3]
    s.lexical.search=lambda *a,**kw:pytest.fail('dense invoked lexical')
    assert s.search({'query':'Title','project_uids':[setup[2]]},allowed_projects=[setup[2]],method='dense')['total']==1
    with pytest.raises(ValueError):s.search({'query':'x','project_uids':[setup[2]]},allowed_projects=[setup[2]],method='bad')


def test_durable_evaluation_and_report(setup):
    q,s,d,item,g=prepared(setup);p=setup[2]
    ds=q.stage_dataset(p,{'cases':[{'query':'Title','relevant_item_uids':[item]}]})
    job=q.enqueue_evaluation(p,ds['dataset_ref'],methods=['keyword','dense','hybrid'],top_k=10)
    with pytest.raises(QualityError,match='REPORT_NOT_READY'):q.report(job['job_id'])
    q=QualityService(q.db,s,d)
    report=finish(q,job)
    assert report['status']=='PASS' and report['report']['generation_refs']=={p:g}
    assert report['report']['methods']['keyword']['precision_at_k']==.1
    assert report['report']['methods']['hybrid']['recall_at_k']==1
    assert q.queue.get_job(job['job_id'])['state']=='SUCCEEDED'


@pytest.mark.parametrize('payload',[{'cases':[]},{'cases':[{'query':' ','relevant_item_uids':['a']}]},{'cases':[{'query':'x','relevant_item_uids':['a','a']}]},{'cases':[{'query':'x','relevant_item_uids':['a'],'url':'https://no'}]}])
def test_strict_dataset_rejection(setup,payload):
    with pytest.raises(ValueError):QualityService(setup[0]).stage_dataset(setup[2],payload)


def test_foreign_relevance_rejected_before_search(setup):
    q,s,d,item,g=prepared(setup);p=setup[2]
    with pytest.raises(QualityError,match='DATASET_ITEM_SCOPE'):q.stage_dataset(p,{'cases':[{'query':'x','relevant_item_uids':['foreign']}]})
    assert not d.calls


def test_generation_drift_does_not_publish_metrics(setup):
    q,s,d,item,g=prepared(setup);p=setup[2]
    ds=q.stage_dataset(p,{'cases':[{'query':'Title','relevant_item_uids':[item]}]})
    job=q.enqueue_evaluation(p,ds['dataset_ref'])
    def drift():
        d.hook=None
        with q.db.transaction() as c:c.execute('UPDATE projects SET active_generation_uid=NULL WHERE project_uid=?',(p,))
    d.hook=drift
    report=finish(q,job)
    assert report['status']=='FAIL' and report['report']['error_code']=='EVALUATION_GENERATION_DRIFT'


def test_integrity_detects_raw_hash_and_keyword_corruption(setup):
    q,s,d,item,g=prepared(setup)
    with q.db.transaction() as c:
        c.execute("UPDATE item_revisions SET hash='bad'")
        c.execute('DELETE FROM keyword_fts')
    report=finish(q,q.enqueue_integrity(setup[2]))
    assert report['status']=='FAIL'
    failed={x['code'] for x in report['report']['checks'] if x['status']=='FAIL'}
    assert {'RAW_HASH','KEYWORD_COVERAGE'}<=failed


def test_no_vector_is_not_verified(setup):
    q,s,d,item,g=prepared(setup);q.vector_store=None
    report=finish(q,q.enqueue_integrity(setup[2]))
    assert next(x for x in report['report']['checks'] if x['code']=='DENSE_COVERAGE')['status']=='NOT VERIFIED'


def test_fenced_old_owner_cannot_publish_report(setup):
    q=QualityService(setup[0]);job=q.enqueue_integrity(setup[2]);claimed=q.queue.claim('old',300)
    with q.db.transaction() as c:c.execute('UPDATE jobs SET fencing_token=? WHERE job_id=?',('replacement',job['job_id']))
    with pytest.raises(LeaseLost):q.run(claimed,lambda:False)
    with pytest.raises(QualityError):q.report(job['job_id'])


def test_clean_local_checks_and_dense_corruption(setup):
    q,s,d,item,g=prepared(setup)
    good=finish(q,q.enqueue_integrity(setup[2]))
    assert good['status']=='NOT VERIFIED'
    assert all(x['status']=='PASS' for x in good['report']['checks'] if x['code']!='LIVE_ALM_COMPLETENESS')
    next(iter(d.points.values()))['vector']=[float('nan'),0.]
    bad=finish(q,q.enqueue_integrity(setup[2]))
    assert next(x for x in bad['report']['checks'] if x['code']=='DENSE_COVERAGE')['status']=='FAIL'


def test_missing_source_fields_detected_even_null_definition_kind(setup):
    q,s,d,item,g=prepared(setup)
    with q.db.transaction() as c:
        c.execute("UPDATE item_revisions SET raw_payload=?",(json.dumps({'id':'1','title':'Title','fields':[{'source_field_id':'lost','raw_value':'retained'}],'attachments':[]}),))
    result=finish(q,q.enqueue_integrity(setup[2]))
    assert next(x for x in result['report']['checks'] if x['code']=='SOURCE_FIELD_VALUES')['status']=='FAIL'


def test_upper_span_bound_detected(setup):
    q,s,d,item,g=prepared(setup)
    with q.db.transaction() as c:
        row=c.execute('SELECT chunk_uid,source_span_offsets FROM chunks LIMIT 1').fetchone()
        spans=json.loads(row['source_span_offsets']);spans[0]['char_end']=10**9
        c.execute('UPDATE chunks SET source_span_offsets=? WHERE chunk_uid=?',(json.dumps(spans),row['chunk_uid']))
    result=finish(q,q.enqueue_integrity(setup[2]))
    assert next(x for x in result['report']['checks'] if x['code']=='CHUNK_BOUNDS')['status']=='FAIL'


def test_table_integrity_clean_span_coordinates(setup):
    db,_,p,r,_=setup
    from almrag.processing import ProcessingPolicy,FieldRef
    setup[4].configure(p,ProcessingPolicy(fields=[FieldRef(kind='NORMALIZED',key='description')]))
    revision=add_item(setup,description='<table><tr><th>A</th></tr><tr><td>가나다</td></tr></table>')
    # Explicit HTML envelope mimics a sanitized collector observation.
    with db.transaction() as c:
        c.execute('DROP TRIGGER immutable_revision_update')
        env=json.loads(c.execute('SELECT raw_payload FROM item_revisions').fetchone()[0]);env['description']['format']='text/html'
        c.execute('UPDATE item_revisions SET raw_payload=?,hash=?',(json.dumps(env),fingerprint({'envelope':env,'attachment_checksums':[]})))
    execute(setup);execute(setup,'EMBED');s,d=service(setup);g=publish(setup,d)
    with db.transaction() as c:
        docs=[dict(row) for row in c.execute('SELECT * FROM keyword_documents ORDER BY point_uuid')]
        c.execute('UPDATE index_publications SET lexical_digest=?',(fingerprint(docs),))
    d.retrieve=lambda collection,ids:[d.points[i] for i in ids]
    q=QualityService(db,s,d);report=finish(q,q.enqueue_integrity(p))
    assert next(x for x in report['report']['checks'] if x['code']=='CHUNK_BOUNDS')['status']=='PASS'


def test_pure_comparison_channels_never_inject_exact_id_metadata(setup):
    q,s,d,item,g=prepared(setup)
    d.query=lambda *args,**kwargs:[]
    s.lexical.search=lambda *args,**kwargs:[]
    request={'query':item,'project_uids':[setup[2]]}
    assert s.search(request,allowed_projects=[setup[2]],method='dense')['total']==0
    assert s.search(request,allowed_projects=[setup[2]],method='keyword')['total']==0
    assert s.search(request,allowed_projects=[setup[2]],method='hybrid')['total']==1
