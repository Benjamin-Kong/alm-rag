"""SRS-048/051/059: operator profile creation never invents model evidence."""
import hashlib
import json
import stat

import httpx
import pytest
from tokenizers import Tokenizer, models, pre_tokenizers
from almrag.config import Settings
from almrag.embedding import LocalTokenizer, ModelError
from almrag.model_setup import prepare_profile

DIGEST='sha256:'+'a'*64


def artifacts(tmp_path):
    token=tmp_path/'tokenizer.json'
    t=Tokenizer(models.WordLevel({'[UNK]':0},unk_token='[UNK]'))
    t.pre_tokenizer=pre_tokenizers.Whitespace()
    t.save(str(token))
    return dict(tokenizer_path=token,tokenizer_sha256=hashlib.sha256(token.read_bytes()).hexdigest(),
                digest=DIGEST,dimension=3,max_input_tokens=128,output=tmp_path/'profile.json')


def transport(args,*,delta=0,digest=DIGEST):
    counter=LocalTokenizer(args['tokenizer_path'],args['tokenizer_sha256'])
    calls=[]
    def handle(req):
        calls.append(req.url.path)
        if req.url.path=='/api/tags':return httpx.Response(200,json={'models':[{'name':'embeddinggemma-2:latest','digest':digest}]})
        if req.url.path=='/api/show':return httpx.Response(200,json={'capabilities':['embedding'],'model_info':{'gemma.context_length':8192}})
        body=json.loads(req.content)
        assert body['truncate'] is False
        return httpx.Response(200,json={'model':'embeddinggemma-2:latest','embeddings':[[1,0,0]],'prompt_eval_count':counter.count(body['input'])+delta})
    return calls,httpx.MockTransport(handle)


def test_offline_profile_portable_private_unverified(tmp_path,monkeypatch):
    args=artifacts(tmp_path)
    monkeypatch.setattr(httpx.Client,'send',lambda *a,**k:pytest.fail('offline network'))
    result=prepare_profile(**args)
    data=json.loads(args['output'].read_text())
    assert data['tokenizer_path']=='tokenizer.json'
    assert data['model']['expected_digest']==DIGEST
    assert set(data)=={'tokenizer_path','tokenizer_sha256','model'}
    assert result['state']=='NOT_VERIFIED' and 'http' not in json.dumps(result)
    assert stat.S_IMODE(args['output'].stat().st_mode)==0o600


def test_refuses_replace_and_requires_explicit_overwrite(tmp_path):
    args=artifacts(tmp_path)
    args['output'].write_text('existing')
    with pytest.raises(ModelError,match='MODEL_PROFILE_EXISTS'):prepare_profile(**args)
    assert args['output'].read_text()=='existing'
    prepare_profile(**args,overwrite=True)
    assert json.loads(args['output'].read_text())['tokenizer_path']=='tokenizer.json'


@pytest.mark.parametrize('kind,code',[('hash','TOKENIZER_ARTIFACT_MISMATCH'),('digest','MODEL_PROFILE_INVALID'),('dimension','MODEL_PROFILE_INVALID'),('model','MODEL_PROFILE_INVALID')])
def test_invalid_inputs_leave_no_profile(tmp_path,kind,code):
    args=artifacts(tmp_path)
    if kind=='hash':args['tokenizer_sha256']='b'*64
    elif kind=='digest':args['digest']='fake'
    elif kind=='dimension':args['dimension']=0
    else:args['model_name']='other-model'
    with pytest.raises(ModelError,match=code):prepare_profile(**args)
    assert not args['output'].exists()


def test_explicit_calibration_test_transport_never_claims_real_verification(tmp_path):
    args=artifacts(tmp_path);calls,mock=transport(args)
    result=prepare_profile(**args,verify=True,settings=Settings(ollama_url='http://model.invalid'),_transport=mock)
    assert calls==['/api/tags','/api/show','/api/embed','/api/embed','/api/tags']
    assert result['state']=='FIXTURE_ONLY'
    assert len(result['calibration_evidence'])==2
    assert 'input' not in result and 'model.invalid' not in json.dumps(result)
    assert 'state' not in json.loads(args['output'].read_text())


@pytest.mark.parametrize('delta,digest,code',[(1,DIGEST,'TOKENIZER_MISMATCH'),(0,'sha256:'+'b'*64,'MODEL_DIGEST_MISMATCH')])
def test_calibration_failure_preserves_existing_file(tmp_path,delta,digest,code):
    args=artifacts(tmp_path);args['output'].write_text('existing')
    _,mock=transport(args,delta=delta,digest=digest)
    with pytest.raises(ModelError,match=code):prepare_profile(**args,overwrite=True,verify=True,settings=Settings(),_transport=mock)
    assert args['output'].read_text()=='existing'


def test_output_cannot_replace_tokenizer(tmp_path):
    args=artifacts(tmp_path);args['output']=args['tokenizer_path']
    original=args['output'].read_bytes()
    with pytest.raises(ModelError,match='MODEL_PROFILE_OUTPUT_INVALID'):prepare_profile(**args,overwrite=True)
    assert args['output'].read_bytes()==original


def test_missing_tokenizer_and_symlink_output_fail_closed(tmp_path):
    args=artifacts(tmp_path)
    args['tokenizer_path'].unlink()
    with pytest.raises(ModelError,match='TOKENIZER_ARTIFACT_UNAVAILABLE'):prepare_profile(**args)
    args=artifacts(tmp_path)
    target=tmp_path/'other';target.write_text('keep')
    args['output'].symlink_to(target)
    with pytest.raises(ModelError,match='MODEL_PROFILE_OUTPUT_INVALID'):prepare_profile(**args,overwrite=True)
    assert target.read_text()=='keep'


def test_verification_resolves_env_auth_and_preserves_private_evidence(tmp_path,monkeypatch):
    args=artifacts(tmp_path);calls,mock=transport(args)
    monkeypatch.setenv('SYNTHETIC_MODEL_SECRET','synthetic-secret-do-not-print')
    def handle(request):
        assert request.headers['Authorization']=='Bearer synthetic-secret-do-not-print'
        return mock.handle_request(request)
    result=prepare_profile(**args,verify=True,settings=Settings(ollama_auth_ref='env:SYNTHETIC_MODEL_SECRET'),
                           _transport=httpx.MockTransport(handle))
    assert calls and 'synthetic-secret' not in json.dumps(result)
    assert 'Authorization' not in args['output'].read_text()


@pytest.mark.parametrize('reference',['env:MISSING_MODEL_SECRET','vault:operator'])
def test_missing_or_unsupported_probe_auth_never_publishes(tmp_path,reference,monkeypatch):
    args=artifacts(tmp_path);calls,mock=transport(args)
    monkeypatch.delenv('MISSING_MODEL_SECRET',raising=False)
    with pytest.raises(ModelError,match='MODEL_CREDENTIAL_UNAVAILABLE'):
        prepare_profile(**args,verify=True,settings=Settings(ollama_auth_ref=reference),_transport=mock)
    assert not calls and not args['output'].exists()


def test_cli_failure_is_sanitized_and_exit_status_nonzero(tmp_path):
    import os
    from pathlib import Path
    import subprocess
    import sys
    args=artifacts(tmp_path)
    command=[sys.executable,'tools/prepare_model_profile.py','--tokenizer',str(args['tokenizer_path']),
             '--tokenizer-sha256','b'*64,'--digest',DIGEST,'--dimension','3','--max-input-tokens','128',
             '--output',str(args['output'])]
    root=Path(__file__).resolve().parents[1]
    run=subprocess.run(command,cwd=root,env={**os.environ,'PYTHONPATH':str(root/'src')},capture_output=True,text=True)
    assert run.returncode==1 and not run.stdout
    assert json.loads(run.stderr)=={'state':'FAIL','code':'TOKENIZER_ARTIFACT_MISMATCH'}
    assert str(tmp_path) not in run.stderr and not args['output'].exists()


def test_created_profile_loads_existing_runtime_offline(tmp_path):
    from almrag.model_runtime import ModelRuntimeRegistry
    args=artifacts(tmp_path);prepare_profile(**args)
    runtime=ModelRuntimeRegistry(Settings(model_profile_path=str(args['output']))).get('synthetic-project')
    assert runtime.config.expected_digest==DIGEST and runtime.profile is None
    with pytest.raises(ModelError,match='MODEL_NETWORK_DISABLED'):runtime.verify_runtime()
