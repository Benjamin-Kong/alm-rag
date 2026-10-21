"""SRS-033/058: strict original JSON types in integrity reports (independent QA repro)."""
import json
import pytest
from almrag.embedding import fingerprint
from test_processing import setup
from test_quality_engine import prepared,finish

@pytest.mark.parametrize('original,corrupted',[(True,1),({'flag':True},{'flag':1}),([False],[0]),(1,1.0)])
def test_integrity_field_comparison_preserves_json_types(setup,original,corrupted):
    q,s,d,item,g=prepared(setup);db,instance,p,_,_=setup
    with db.transaction() as c:
        row=c.execute('SELECT revision_uid,raw_payload FROM item_revisions').fetchone()
        raw=json.loads(row['raw_payload']);raw['fields']=[{'source_field_id':'flag','raw_value':original}]
        c.execute('UPDATE item_revisions SET raw_payload=?,hash=? WHERE revision_uid=?',(json.dumps(raw),fingerprint({'envelope':raw,'attachment_checksums':[]}),row['revision_uid']))
        c.execute("INSERT INTO field_definitions(field_def_uid,instance_uid,scope,source_field_id) VALUES('flag',?,'project','flag')",(instance,))
        c.execute("INSERT INTO field_values(revision_uid,field_def_uid,raw_value) VALUES(?,'flag',?)",(row['revision_uid'],json.dumps(corrupted)))
    report=finish(q,q.enqueue_integrity(p))
    assert next(x for x in report['report']['checks'] if x['code']=='SOURCE_FIELD_VALUES')['status']=='FAIL'

def test_queued_quality_snapshot_is_immutable_and_corruption_detected(setup):
    import sqlite3
    q,s,d,item,g=prepared(setup);p=setup[2]
    ds=q.stage_dataset(p,{'cases':[{'query':'Title','relevant_item_uids':[item]}]})
    job=q.enqueue_evaluation(p,ds['dataset_ref'])
    with pytest.raises(sqlite3.IntegrityError,match='immutable'):
        with q.db.transaction() as c:c.execute('UPDATE quality_requests SET snapshot=? WHERE job_id=?',('{}',job['job_id']))
    # Explicitly simulate storage corruption after bypassing the normal immutability boundary.
    with q.db.transaction() as c:
        c.execute('DROP TRIGGER quality_request_immutable')
        payload=json.loads(c.execute('SELECT snapshot FROM quality_requests WHERE job_id=?',(job['job_id'],)).fetchone()[0]);payload['top_k']=1
        c.execute('UPDATE quality_requests SET snapshot=? WHERE job_id=?',(json.dumps(payload),job['job_id']))
    report=finish(q,job)
    assert report['status']=='FAIL' and report['report']['error_code']=='QUALITY_SNAPSHOT_INTEGRITY'

def test_normalized_same_length_text_corruption_is_detected(setup):
    q,s,d,item,g=prepared(setup)
    with q.db.transaction() as c:c.execute("UPDATE content_blocks SET normalized_text=replace(normalized_text,'Title','ZZZZZ') WHERE normalized_text LIKE '%Title%'")
    report=finish(q,q.enqueue_integrity(setup[2]))
    assert report['status']=='FAIL'

def test_empty_chunk_provenance_is_detected(setup):
    q,s,d,item,g=prepared(setup)
    with q.db.transaction() as c:c.execute("UPDATE chunks SET source_span_offsets='[]',row_ids='[]'")
    report=finish(q,q.enqueue_integrity(setup[2]))
    assert report['status']=='FAIL'

def test_normalized_table_cell_corruption_is_detected(setup):
    from test_processing import add_item,execute
    from test_retrieval import publish,service
    from almrag.quality import QualityService
    db,_,p,_,_=setup;revision=add_item(setup,description='<table><tr><th>H</th></tr><tr><td>value</td></tr></table>')
    with db.transaction() as c:
        c.execute('DROP TRIGGER immutable_revision_update');raw=json.loads(c.execute('SELECT raw_payload FROM item_revisions').fetchone()[0]);raw['description']['format']='text/html'
        c.execute('UPDATE item_revisions SET raw_payload=?,hash=?',(json.dumps(raw),fingerprint({'envelope':raw,'attachment_checksums':[]})))
    execute(setup);execute(setup,'EMBED');search,dense=service(setup);generation=publish(setup,dense)
    with db.transaction() as c:
        docs=[dict(r) for r in c.execute('SELECT * FROM keyword_documents ORDER BY point_uuid')];c.execute('UPDATE index_publications SET lexical_digest=?',(fingerprint(docs),))
    dense.retrieve=lambda collection,ids:[dense.points[x] for x in ids]
    q=QualityService(db,search,dense)
    clean=finish(q,q.enqueue_integrity(p));assert clean['status']=='NOT VERIFIED'
    with db.transaction() as c:
        row=c.execute("SELECT block_uid,table_json FROM content_blocks WHERE type='table'").fetchone();table=json.loads(row['table_json']);table['cells'][-1]['text']='wrong'
        c.execute('UPDATE content_blocks SET table_json=? WHERE block_uid=?',(json.dumps(table),row['block_uid']))
    report=finish(q,q.enqueue_integrity(p));assert report['status']=='FAIL'

def test_corruption_report_identifies_item_revision_and_explicit_recovery_step(setup):
    q,s,d,item,g=prepared(setup)
    with q.db.transaction() as c:c.execute("UPDATE content_blocks SET normalized_text=replace(normalized_text,'Title','ZZZZZ') WHERE normalized_text LIKE '%Title%'")
    report=finish(q,q.enqueue_integrity(setup[2]))
    finding=next(x for x in report['report']['issues'] if x['code']=='TRANSFORMATION_CONTENT')
    assert finding['item_uid']==item and finding['revision_uid']
    assert finding['recommended_action']=='RECOVER_TRUSTED_RAW_AND_REPROCESS'
    assert 'raw_payload' not in json.dumps(report['report']['issues'])
