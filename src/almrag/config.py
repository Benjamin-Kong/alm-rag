"""Validated configuration; importing this module never contacts a service."""
import os
from dataclasses import dataclass, field
from typing import Literal
from urllib.parse import urlsplit

from pydantic import BaseModel, ConfigDict, model_validator


def endpoint(value: str) -> str:
    parts = urlsplit(value)
    if parts.scheme not in {'http', 'https'} or not parts.hostname or parts.username or parts.password or parts.query or parts.fragment:
        raise ValueError('invalid_service_url')
    return value.rstrip('/')


@dataclass(frozen=True)
class Settings:
    database_path: str = 'data/alm.sqlite'
    ollama_url: str = 'http://127.0.0.1:11434'
    qdrant_url: str = 'http://127.0.0.1:6333'
    embedding_model: str = 'embeddinggemma-2'
    master_key: str = field(default='', repr=False)
    allowed_origin: str = 'https://localhost:8443'
    session_seconds: int = 3600
    tls_verify: bool = True
    ca_bundle: str | None = None
    ollama_auth_ref: str | None = None
    qdrant_auth_ref: str | None = None

    def __post_init__(self):
        endpoint(self.ollama_url)
        endpoint(self.qdrant_url)
        origin = urlsplit(endpoint(self.allowed_origin))
        if origin.path or self.session_seconds < 1:
            raise ValueError('invalid_security_settings')

    @classmethod
    def from_env(cls):
        return cls(database_path=os.getenv('ALMRAG_DATABASE_PATH', 'data/alm.sqlite'),
                   ollama_url=os.getenv('ALMRAG_OLLAMA_BASE_URL', 'http://127.0.0.1:11434'),
                   qdrant_url=os.getenv('ALMRAG_QDRANT_URL', 'http://127.0.0.1:6333'),
                   master_key=os.getenv('ALMRAG_MASTER_KEY', ''),
                   allowed_origin=os.getenv('ALMRAG_ALLOWED_ORIGIN', 'https://localhost:8443'),
                   ca_bundle=os.getenv('ALMRAG_CA_BUNDLE'),
                   ollama_auth_ref=os.getenv('ALMRAG_OLLAMA_AUTH_REF'),
                   qdrant_auth_ref=os.getenv('ALMRAG_QDRANT_AUTH_REF'))


class SourceProfile(BaseModel):
    model_config = ConfigDict(extra='forbid')
    source_type: Literal['codebeamer', 'polarion']
    base_url: str
    scope_kind: Literal['TRACKER', 'WORK_ITEM_TYPE']

    @model_validator(mode='after')
    def validate_source(self):
        endpoint(self.base_url)
        expected = 'TRACKER' if self.source_type == 'codebeamer' else 'WORK_ITEM_TYPE'
        if self.scope_kind != expected:
            raise ValueError('source_scope_mismatch')
        return self
