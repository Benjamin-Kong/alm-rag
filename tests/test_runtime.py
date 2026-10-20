"""SRS-017/026/038/040/057: offline service and worker entrypoint contracts."""
import json
import httpx
import pytest

from almrag.config import Settings
from almrag.services import ServiceProbe
from almrag.worker import run_once, write_health, healthy


def test_remote_service_auth_injected_without_leaking_errors():
    requests=[]
    def handler(request):
        requests.append(request)
        return httpx.Response(200,json={'models':[]})
    settings=Settings(ollama_url='https://ollama.example.invalid',ollama_auth_ref='ollama-ref')
    probe=ServiceProbe(settings,secret_resolver=lambda ref:'synthetic-token',transport=httpx.MockTransport(handler))
    assert probe.check('ollama') == {'service':'ollama','available':True}
    assert requests[0].headers['Authorization']=='Bearer synthetic-token'
    assert requests[0].url.path=='/api/tags'
    denied=ServiceProbe(settings,secret_resolver=lambda ref:'synthetic-token',transport=httpx.MockTransport(lambda _:httpx.Response(401,text='sensitive remote body')))
    assert denied.check('ollama') == {'service':'ollama','available':False}
    assert 'sensitive' not in json.dumps(denied.check('ollama'))


def test_worker_never_succeeds_an_unimplemented_stage(tmp_path):
    class Queue:
        def __init__(self): self.finished=[]
        def claim(self,owner,lease_seconds=30): return {'job_id':'j1','fencing_token':'t1','stage':'COLLECT'}
        def finish(self,job_id,token,state='SUCCEEDED',error_code=None): self.finished.append((job_id,token,state,error_code))
    queue=Queue()
    assert run_once(queue,'synthetic-worker') is True
    assert queue.finished == [('j1','t1','BLOCKED','STAGE_UNAVAILABLE')]
    path=tmp_path/'heartbeat.json'
    assert not healthy(path,now=100)
    write_health(path,now=100)
    assert healthy(path,now=110)
    assert not healthy(path,now=200)
