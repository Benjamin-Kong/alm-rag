"""SRS-042: allowlisted summary outbox, explicit network disable, idempotent retries."""
import pytest
from almrag.storage import Database
from almrag.docs_publish import Summary,SummaryOutbox


def test_allowlisted_summary_rejects_source_text_and_publication_is_opt_in(tmp_path):
    db=Database(tmp_path/'db');db.migrate()
    safe=dict(commit='a'*40,milestone='M5',status='IN_PROGRESS',srs_ids=['SRS-042'],passed=10,failed=0,not_verified=2)
    with pytest.raises(ValueError):Summary.model_validate({**safe,'raw_item':'confidential text'})
    outbox=SummaryOutbox(db)
    first=outbox.enqueue(safe);assert outbox.enqueue(safe)==first
    assert outbox.flush()=={'sent':0,'failed':0,'disabled':True}
    calls=[];publisher=SummaryOutbox(db,send=lambda payload:calls.append(payload),enabled=True)
    assert publisher.flush()['sent']==1 and len(calls)==1
    assert publisher.flush()['sent']==0
    assert set(calls[0])==set(safe)


def test_mock_publisher_failure_retries_without_leaking_exception(tmp_path):
    db=Database(tmp_path/'db');db.migrate();attempts=[]
    def fail(payload):attempts.append(1);raise ValueError('secret raw customer text')
    outbox=SummaryOutbox(db,send=fail,enabled=True)
    outbox.enqueue(dict(commit='b'*40,milestone='M5',status='QUALITY_REVIEW',srs_ids=['SRS-042'],passed=0,failed=1,not_verified=1))
    assert outbox.flush()=={'sent':0,'failed':1,'disabled':False}
    with db.connect() as c:
        row=c.execute('SELECT * FROM doc_summary_outbox').fetchone()
        assert row['state']=='PENDING' and row['error_code']=='PUBLISH_RETRY_PENDING'
        assert 'secret' not in str(dict(row))
    outbox.send=lambda payload:attempts.append(2)
    assert outbox.flush()['sent']==1 and attempts==[1,2]


def test_busy_outbox_releases_its_own_descriptor(tmp_path,monkeypatch):
    import almrag.docs_publish as module
    db=Database(tmp_path/'db');db.migrate();closed=[]
    class Busy:
        def __init__(self,path):pass
        def acquire(self):return False
        def close(self):closed.append(True)
    monkeypatch.setattr(module,'_SlotLock',Busy)
    assert SummaryOutbox(db,send=lambda x:None,enabled=True).flush()['sent']==0
    assert closed==[True]


def test_notion_sender_is_network_disabled_and_retry_deduplicates_ack_loss():
    import httpx,json
    from almrag.docs_publish import NotionSummarySender
    summary=Summary(commit='a'*40,milestone='M5',status='IN_PROGRESS',srs_ids=['SRS-042'],passed=1,failed=0,not_verified=2).model_dump()
    sender=NotionSummarySender('3fe8be2f-eeee-81d4-ad48-cddc61ba0f5c',lambda:'synthetic-token')
    with pytest.raises(ValueError,match='PUBLISH_NETWORK_DISABLED'):sender(summary)
    blocks=[];calls=[];lost=[True]
    def handler(request):
        calls.append(request.method)
        if request.method=='GET':return httpx.Response(200,json={'results':blocks,'has_more':False,'next_cursor':None})
        assert request.headers['authorization']=='Bearer synthetic-token'
        body=json.loads(request.content);blocks.extend(body['children'])
        if lost.pop() if lost else False:raise httpx.ReadError('secret exception')
        return httpx.Response(200,json={'results':blocks})
    sender=NotionSummarySender('3fe8be2f-eeee-81d4-ad48-cddc61ba0f5c',lambda:'synthetic-token',transport=httpx.MockTransport(handler))
    with pytest.raises(ValueError,match='PUBLISH_UNAVAILABLE'):sender(summary)
    sender(summary)
    assert calls==['GET','PATCH','GET'] and len(blocks)==1


def test_configured_automatic_publisher_reuses_disabled_default_and_safe_secret_ref(tmp_path,monkeypatch):
    from almrag.config import Settings
    from almrag.worker import _ConfiguredCollection
    import almrag.docs_publish as module
    from almrag.connection import Connections
    db=Database(tmp_path/'db');db.migrate();calls=[]
    settings=Settings(database_path=str(db.path),notion_summary_enabled=True,notion_auth_ref='env:NOTION_TEST')
    monkeypatch.setattr(Connections,'secret',lambda self,ref:'synthetic' if ref=='env:NOTION_TEST' else None)
    class Sender:
        def __init__(self,root,resolver,**kwargs):assert resolver()=='synthetic'
        def __call__(self,payload):calls.append(payload)
    monkeypatch.setattr(module,'NotionSummarySender',Sender)
    SummaryOutbox(db).enqueue(dict(commit='c'*40,milestone='M5',status='IN_PROGRESS',srs_ids=['SRS-042'],passed=1,failed=0,not_verified=1))
    worker=_ConfiguredCollection(db,settings);worker.cleanup_pending()
    assert len(calls)==1
    assert Settings().notion_summary_enabled is False
