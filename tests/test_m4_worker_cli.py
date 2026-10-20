"""SRS-018/024/056: index worker stages and UI-independent search commands."""
import pytest
from typer.testing import CliRunner
from almrag import cli
from almrag.queue import Queue
from almrag.storage import Database
from almrag.worker import run_once


@pytest.mark.parametrize('stage',['INDEX','REBUILD'])
def test_worker_index_stage_dispatch(tmp_path,stage):
    db=Database(tmp_path/'db');db.migrate();i=db.add_instance('codebeamer','https://fixture.invalid','f','env:F');p=db.add_project(i,'p','P');q=Queue(db);queued=q.enqueue(p,stage)
    class Service:
        def run(self,job,abort_check):
            assert job['stage']==stage and not abort_check();q.finish(job['job_id'],job['fencing_token'],'SUCCEEDED')
    assert run_once(q,'test',index_service=Service())
    assert q.get_job(queued['job_id'])['state']=='SUCCEEDED'


def test_search_index_detail_cli_paths(monkeypatch):
    calls=[];monkeypatch.setattr(cli,'request',lambda *args:calls.append(args))
    runner=CliRunner()
    for args in [['search','SOME/IP-SD','--project','p','--top-k','2'],['item','id/space'],['index','p'],['rebuild-index','p'],['index-preflight','p','--stage','REBUILD_INDEX']]:
        result=runner.invoke(cli.app,args);assert result.exit_code==0,result.output
    assert calls[0][0:2]==('POST','/search')
    assert calls[0][2]['project_uids']==['p'] and calls[0][2]['query']=='SOME/IP-SD' and calls[0][2]['top_k']==2
    assert calls[1]==('GET','/items/id%2Fspace')
    assert calls[2][2]['stage']=='INDEX' and calls[3][2]['stage']=='REBUILD_INDEX'
    assert calls[4]==('POST','/projects/p/index-preflight?stage=REBUILD_INDEX')


def test_pipeline_failure_cli_paths(monkeypatch):
    calls=[];monkeypatch.setattr(cli,'request',lambda *args:calls.append(args));runner=CliRunner()
    commands=[['pipeline-preflight','p'],['sync','p','--config-revision','pinned'],['failed-items','job/id','--limit','2','--offset','1'],['retry-item','j','item/id','--from-stage','PROCESS','--expected-revision-uid','rev'],['retry-failed-items','j','--force-recollect'],['resume','j']]
    for args in commands:
        result=runner.invoke(cli.app,args);assert result.exit_code==0,result.output
    assert calls[0]==('POST','/projects/p/pipeline-preflight')
    assert calls[1][2]=={'stage':'SYNC','config_revision':'pinned'}
    assert calls[2]==('GET','/jobs/job%2Fid/failed-items?limit=2&offset=1')
    assert calls[3]==('POST','/jobs/j/failed-items/item%2Fid/retry',{'from_stage':'PROCESS','force_recollect':False,'expected_revision_uid':'rev'})
    assert calls[4][1]=='/jobs/j/failed-items/retry' and calls[4][2]['force_recollect'] is True
    assert calls[5]==('POST','/jobs/j/resume')


def test_search_cli_exact_id_scope_and_metadata_filters(monkeypatch):
    calls=[];monkeypatch.setattr(cli,'request',lambda *args:calls.append(args))
    result=CliRunner().invoke(cli.app,['search','x','--project','p','--item-uid','item-1','--item-uid','item-2','--source-item-id','REQ-007','--scope','tracker-1','--filters','{"fields":[{"kind":"NORMALIZED","key":"status","value":"open"}]}'])
    assert result.exit_code==0,result.output
    assert calls[0][2]['filters']=={'item_uids':['item-1','item-2'],'source_item_ids':['REQ-007'],'source_scope_ids':['tracker-1'],'fields':[{'kind':'NORMALIZED','key':'status','value':'open'}]}


@pytest.mark.parametrize('raw',['not-json','[]','{"item_uids":["a"],"item_uids":["b"]}','{"fields":[{"kind":"SOURCE","key":"x","value":NaN}]}'])
def test_search_cli_invalid_filter_json_rejected_without_network(monkeypatch,raw):
    calls=[];monkeypatch.setattr(cli,'request',lambda *args:calls.append(args))
    result=CliRunner().invoke(cli.app,['search','x','--project','p','--filters',raw])
    assert result.exit_code==1
    assert 'Invalid search filters.' in result.output
    assert not calls


def test_search_cli_conflicting_filter_flags_rejected_without_network(monkeypatch):
    calls=[];monkeypatch.setattr(cli,'request',lambda *args:calls.append(args))
    result=CliRunner().invoke(cli.app,['search','x','--project','p','--item-uid','new','--filters','{"item_uids":["old"]}'])
    assert result.exit_code==1 and not calls


def test_deferred_index_cleanup_diagnostic_is_sanitized():
    from almrag.security import safe_event
    event=safe_event(action='index_cleanup',outcome='deferred',error_code='CLEANUP_RETRY_PENDING',secret='never-publish',message='untrusted raw transport details')
    assert event['action']=='index_cleanup'
    assert event['outcome']=='deferred'
    assert event['error_code']=='CLEANUP_RETRY_PENDING'
    assert 'secret' not in event and 'message' not in event
