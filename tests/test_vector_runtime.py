"""SRS-018/019/059: no vector calls or secret access until a supported operation."""
import pytest
from almrag.config import Settings
from almrag.vector_runtime import VectorRuntimeRegistry
from almrag.vector_store import VectorError


def test_vector_runtime_network_defaults_off(monkeypatch):
    assert not Settings().live_vector_enabled
    monkeypatch.setenv('ALMRAG_LIVE_VECTOR_ENABLED','true')
    assert Settings.from_env().live_vector_enabled


def test_vector_runtime_does_not_resolve_credentials_during_construction():
    seen=[]
    runtime=VectorRuntimeRegistry(Settings(qdrant_auth_ref='env:SYNTHETIC'),secret_resolver=lambda ref:seen.append(ref) or 'synthetic')
    assert seen==[]
    with pytest.raises(VectorError,match='VECTOR_NETWORK_DISABLED'):
        runtime.ensure_collection('almrag_'+'a'*32,2)
    assert seen==['env:SYNTHETIC']


def test_credential_errors_do_not_echo_private_text():
    runtime=VectorRuntimeRegistry(Settings(qdrant_auth_ref='env:MISSING'),secret_resolver=lambda _:(_ for _ in ()).throw(ValueError('private-secret')))
    with pytest.raises(VectorError) as failure:runtime.ensure_collection('almrag_'+'a'*32,2)
    assert failure.value.code=='VECTOR_CREDENTIAL_UNAVAILABLE' and 'private-secret' not in str(failure.value)


def test_lazy_vector_runtime_forwards_job_abort_before_any_request():
    runtime=VectorRuntimeRegistry(Settings())
    runtime.abort_check=lambda:True
    with pytest.raises(VectorError,match='ABORTED'):
        runtime.ensure_collection('almrag_'+'a'*32,2)
