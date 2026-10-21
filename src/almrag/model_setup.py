"""Offline-first operator artifact setup; runtime evidence is never profile input."""
import json
import os
from pathlib import Path
import re
import ssl
import tempfile

from pydantic import ValidationError

from almrag.config import Settings
from almrag.connection import Connections
from almrag.embedding import LocalTokenizer, ModelConfig, ModelError, OllamaEmbedder
from almrag.model_runtime import LocalModelProfile


def _publish(path, data, overwrite):
    """Publish complete private file, with atomic exclusive creation by default."""
    temporary=None
    try:
        fd,temporary=tempfile.mkstemp(prefix='.model-profile-',dir=path.parent)
        with os.fdopen(fd,'wb') as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        if overwrite:
            os.replace(temporary,path)
        else:
            try:os.link(temporary,path)
            except FileExistsError:raise ModelError('MODEL_PROFILE_EXISTS') from None
    except ModelError:raise
    except OSError:raise ModelError('MODEL_PROFILE_WRITE_FAILED') from None
    finally:
        if temporary is not None:
            try:os.unlink(temporary)
            except FileNotFoundError:pass


def prepare_profile(*,tokenizer_path,tokenizer_sha256,digest,dimension,max_input_tokens,
                    output,model_name='embeddinggemma-2',overwrite=False,verify=False,
                    settings=None,_transport=None):
    """Validate before publication. `_transport` is test-only, always FIXTURE_ONLY.

    Files contain LocalModelProfile only, never a reusable VERIFIED assertion.
    Every worker still performs its own digest/context/count calibration.
    """
    path=Path(output).absolute()
    token_path=Path(tokenizer_path).resolve()
    if path.is_symlink() or path.resolve()==token_path:
        raise ModelError('MODEL_PROFILE_OUTPUT_INVALID')
    if path.exists() and not overwrite:raise ModelError('MODEL_PROFILE_EXISTS')
    try:
        model=ModelConfig(model_name=model_name,expected_digest=digest,vector_dimension=dimension,
                          effective_max_input_tokens=max_input_tokens)
        profile=LocalModelProfile(model=model,tokenizer_path=os.path.relpath(token_path,path.parent.resolve()),
                                  tokenizer_sha256=tokenizer_sha256)
    except (ValidationError,ValueError,TypeError):raise ModelError('MODEL_PROFILE_INVALID') from None
    tokenizer=LocalTokenizer(token_path,profile.tokenizer_sha256)
    evidence={'state':'NOT_VERIFIED','tokenizer_id':tokenizer.identity,'model_digest':model.expected_digest}
    if verify:
        settings=settings or Settings.from_env()
        try:
            tls=ssl.create_default_context(cafile=settings.ca_bundle) if settings.tls_verify else False
        except (OSError,ValueError):raise ModelError('MODEL_TLS_CONFIG_INVALID') from None
        headers={}
        if settings.ollama_auth_ref:
            # This setup tool is DB-free. Runtime also supports its encrypted
            # vault; use an environment reference for the operator probe.
            if not re.fullmatch(r'env:[A-Z][A-Z0-9_]*',settings.ollama_auth_ref):
                raise ModelError('MODEL_CREDENTIAL_UNAVAILABLE')
            try:secret=Connections(None,settings).secret(settings.ollama_auth_ref)
            except (ValueError,OSError):raise ModelError('MODEL_CREDENTIAL_UNAVAILABLE') from None
            headers={'Authorization':'Bearer '+secret}
        runtime=OllamaEmbedder(settings.ollama_url,model,tokenizer,allow_live=True,
            transport=_transport,allow_fixture=_transport is not None,auth_headers=headers,verify=tls)
        evidence=runtime.verify_runtime()
    _publish(path,(profile.model_dump_json(indent=2)+'\n').encode(),overwrite)
    # No paths, endpoints, source text or credentials enter CLI evidence.
    return json.loads(json.dumps(evidence,allow_nan=False))
