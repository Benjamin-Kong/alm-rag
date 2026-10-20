"""SRS-017/038/044: local/remote configuration without network side effects."""
import pytest
from almrag.config import Settings, SourceProfile


def test_settings_validate_endpoints_and_never_display_secret():
    settings = Settings(ollama_url='https://ollama.example.invalid', qdrant_url='http://127.0.0.1:6333', master_key='synthetic-secret')
    assert settings.embedding_model == 'embeddinggemma-2'
    assert 'synthetic-secret' not in repr(settings)
    for url in ['file:///tmp/data', 'https://user:password@host', 'http://host/?token=secret']:
        with pytest.raises(ValueError):
            Settings(ollama_url=url)


def test_source_specific_profiles_reject_wrong_scope():
    assert SourceProfile(source_type='codebeamer', base_url='https://cb.example.invalid', scope_kind='TRACKER').source_type == 'codebeamer'
    assert SourceProfile(source_type='polarion', base_url='https://po.example.invalid', scope_kind='WORK_ITEM_TYPE').source_type == 'polarion'
    with pytest.raises(ValueError):
        SourceProfile(source_type='polarion', base_url='https://po.example.invalid', scope_kind='TRACKER')
