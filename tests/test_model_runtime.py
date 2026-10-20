"""SRS-017/048: explicit local artifacts and runtime opt-in, never auto-download."""
import hashlib
import json
import pytest
from almrag.config import Settings
from almrag.embedding import ModelError


def test_missing_runtime_profile_fails_closed():
    from almrag.model_runtime import ModelRuntimeRegistry
    with pytest.raises(ModelError,match='MODEL_PROFILE_UNCONFIGURED'):
        ModelRuntimeRegistry(Settings()).get('project')


def test_local_profile_cannot_claim_verified_and_network_is_off(tmp_path):
    from tokenizers import Tokenizer,models
    from almrag.model_runtime import ModelRuntimeRegistry
    tokenizer=tmp_path/'tokenizer.json'
    Tokenizer(models.WordLevel({'[UNK]':0},unk_token='[UNK]')).save(str(tokenizer))
    profile={'model':{'expected_digest':'sha256:'+'a'*64},'tokenizer_path':'tokenizer.json','tokenizer_sha256':hashlib.sha256(tokenizer.read_bytes()).hexdigest()}
    path=tmp_path/'profile.json';path.write_text(json.dumps(profile))
    settings=Settings(model_profile_path=str(path))
    registry=ModelRuntimeRegistry(settings)
    client=registry.get('project')
    assert client.profile is None
    with pytest.raises(ModelError,match='MODEL_NETWORK_DISABLED'):client.verify_runtime()
    assert registry.get('other-project') is not client  # abort callbacks never leak between jobs.
    profile['verified']=True;path.write_text(json.dumps(profile))
    with pytest.raises(ModelError,match='MODEL_PROFILE_INVALID'):registry.get('project')


def test_model_settings_default_to_no_live_network(monkeypatch):
    assert Settings.from_env().live_model_enabled is False
    monkeypatch.setenv('ALMRAG_MODEL_PROFILE_PATH','/synthetic/profile.json')
    monkeypatch.setenv('ALMRAG_LIVE_MODEL_ENABLED','true')
    settings=Settings.from_env()
    assert settings.live_model_enabled and settings.model_profile_path=='/synthetic/profile.json'
