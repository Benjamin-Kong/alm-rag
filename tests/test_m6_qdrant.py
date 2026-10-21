"""SRS-033/034/039: actual isolated Qdrant integrity/evaluation, synthetic model/source."""
import json,os
import pytest
from test_pipeline import setup,collection_setup,run
from test_qdrant_local import vector
from test_quality_engine import finish
from almrag.quality import QualityService
from almrag.retrieval import SearchService

pytestmark=pytest.mark.skipif(not os.getenv('ALMRAG_TEST_QDRANT_URL'),reason='dedicated synthetic local Qdrant not explicitly enabled')

def test_actual_qdrant_quality_report_detects_remote_vector_corruption(setup,vector):
    db,adapter,p,runtime,pipeline,index=setup;index.vector_store=vector
    assert run(setup)[0]=='SUCCEEDED'
    search=SearchService(db,lambda _:runtime,vector,allow_fixture=True)
    quality=QualityService(db,search,vector,attachment_root=pipeline.collection.attachment_root)
    with db.connect() as c:
        items=[row[0] for row in c.execute('SELECT item_uid FROM items WHERE project_uid=?',(p,))]
        generation=c.execute('SELECT active_generation_uid FROM projects WHERE project_uid=?',(p,)).fetchone()[0]
        config=c.execute('SELECT collection_name FROM generation_configs WHERE generation_uid=?',(generation,)).fetchone()[0]
        point=json.loads(c.execute('SELECT dense_evidence FROM index_publications WHERE generation_uid=? LIMIT 1',(generation,)).fetchone()[0])[0]
    dataset=quality.stage_dataset(p,{'cases':[{'query':'Title','relevant_item_uids':items}]})
    report=finish(quality,quality.enqueue_evaluation(p,dataset['dataset_ref']))
    assert report['status']=='PASS'
    assert all(method['recall_at_k']==1 for method in report['report']['methods'].values())
    clean=finish(quality,quality.enqueue_integrity(p))
    assert clean['status']=='NOT VERIFIED'
    assert next(x for x in clean['report']['checks'] if x['code']=='DENSE_COVERAGE')['status']=='PASS'
    vector.upsert(config,[{**point,'vector':[1.,0.]}])
    broken=finish(quality,quality.enqueue_integrity(p))
    assert broken['status']=='FAIL'
    assert next(x for x in broken['report']['checks'] if x['code']=='DENSE_COVERAGE')['status']=='FAIL'
    issue=next(x for x in broken['report']['issues'] if x['code']=='DENSE_COVERAGE')
    assert issue['item_uid'] in items and issue['recommended_action']=='REBUILD_INDEX'
