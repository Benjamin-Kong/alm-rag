"""Offline runtime-only M2 smoke; synthetic source + temporary SQLite/assets.

Run inside the backend image with --network none. No pytest/dev dependency.
"""
from pathlib import Path
from tempfile import TemporaryDirectory
import json
import httpx

from almrag.collection import CollectionService
from almrag.config import Settings
from almrag.connection import Connections, PROFILE_ADAPTER
from almrag.connectors import ConnectorError
from almrag.queue import Queue
from almrag.storage import Database
from almrag.worker import run_once


def main():
    calls=[]
    routes={
        '/v3/projects':[{'id':1,'name':'Synthetic'}],
        '/v3/projects/1/trackers':[{'id':31,'name':'Requirements'}],
        '/v3/trackers/31/fields':[{'id':3,'name':'Name'},{'id':80,'name':'Description'}],
        '/v3/trackers/31/items':[{'id':100,'version':1}],
        '/v3/items/100':{'id':100,'version':1,'tracker':{'id':31},'name':'Synthetic','description':'Original','descriptionFormat':'PlainText'},
        '/v3/items/100/relations':{},
        '/v3/items/100/attachments':[{'id':7,'name':'../../fixture.bin'}],
    }
    def handler(request):
        assert request.method=='GET'
        calls.append(request.url.path)
        if request.url.path=='/v3/attachments/7/content':return httpx.Response(200,content=b'synthetic-bytes')
        return httpx.Response(200,json=routes[request.url.path])
    with TemporaryDirectory(prefix='almrag-m2-offline-') as temporary:
        root=Path(temporary)
        settings=Settings(database_path=str(root/'data/fixture.sqlite'))
        db=Database(settings.database_path);db.migrate();db.migrate()
        connections=Connections(db,settings,transport_factory=lambda _:httpx.MockTransport(handler),secret_resolver=lambda _:'synthetic-token')
        profile=PROFILE_ADAPTER.validate_python({'source_type':'codebeamer','base_url':'https://alm.example.invalid:443','display_name':'Synthetic','auth_ref':'env:FIXTURE',
            'http_policy':{'requests_per_second':1000,'burst':100,'min_interval_ms':0}})
        uid=connections.register(profile)['instance_uid']
        service=CollectionService(db,connections.connector,settings.attachment_directory)
        project=service.configure_project(uid,'1','Synthetic')
        pre=service.preflight(project)
        assert pre['collect_ready'] and not pre['sync_ready']
        for _ in range(2):
            queued=service.enqueue(project,pre['config_revision'])
            assert run_once(Queue(db),'smoke',service)
            assert Queue(db).get_job(queued['job_id'])['state']=='SUCCEEDED'
        with db.connect() as c:
            assert [row[0] for row in c.execute('SELECT version FROM schema_migrations ORDER BY version')]==[1,2,3,4,5,6,7,8,9]
            assert c.execute('SELECT count(*) FROM item_revisions').fetchone()[0]==1
            assert c.execute('SELECT active_revision_uid FROM items').fetchone()[0] is None
            assert json.loads(c.execute('SELECT raw_payload FROM item_revisions').fetchone()[0])['raw']==routes['/v3/items/100']
            assert Path(c.execute('SELECT disk_path FROM attachments').fetchone()[0]).read_bytes()==b'synthetic-bytes'
        live=Connections(db,settings,secret_resolver=lambda _:'synthetic-token')
        try:live.connector(uid).probe()
        except ConnectorError as error:assert error.code=='LIVE_ALM_DISABLED'
        else:raise AssertionError('live source must remain disabled')
    print('M2_OFFLINE_RUNTIME_PASS',len(calls),'synthetic GET requests')


if __name__=='__main__':main()
