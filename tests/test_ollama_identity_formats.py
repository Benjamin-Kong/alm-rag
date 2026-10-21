"""SRS-048/051/059: official Ollama tag identity formats retain digest pinning."""
import pytest
from almrag.embedding import ModelConfig, ModelError, OllamaEmbedder

HASH='a'*64


def identity(name,digest,configured='embeddinggemma-2'):
    runtime=OllamaEmbedder('http://synthetic.invalid',ModelConfig(model_name=configured,expected_digest='sha256:'+HASH),object())
    runtime._request=lambda *_:{'models':[{'name':name,'digest':digest}]}
    return runtime._digest()


@pytest.mark.parametrize('name,digest',[
    ('embeddinggemma-2',HASH),
    ('embeddinggemma-2:latest',HASH),
    ('embeddinggemma-2','sha256:'+HASH),
    ('embeddinggemma-2:latest','sha256:'+HASH),
])
def test_official_bare_model_and_raw_digest_match_pinned_canonical_identity(name,digest):
    assert identity(name,digest)=='sha256:'+HASH


def test_explicit_latest_and_bare_default_are_equivalent_only():
    assert identity('embeddinggemma-2',HASH,configured='embeddinggemma-2:latest')=='sha256:'+HASH
    assert identity('embeddinggemma-2:approved',HASH,configured='embeddinggemma-2:approved')=='sha256:'+HASH
    with pytest.raises(ModelError,match='MODEL_UNAVAILABLE'):
        identity('embeddinggemma-2:other',HASH,configured='embeddinggemma-2:approved')
    with pytest.raises(ModelError,match='MODEL_UNAVAILABLE'):
        identity('embeddinggemma-2',HASH,configured='embeddinggemma-2:approved')


@pytest.mark.parametrize('digest',['b'*64,'sha256:'+'b'*64,'a'*63,'a'*65,'A'*64,'sha256:bad','SHA256:'+'a'*64,' '+HASH,None,True,{}])
def test_different_or_malformed_server_digest_fails_closed(digest):
    with pytest.raises(ModelError,match='MODEL_DIGEST_MISMATCH'):
        identity('embeddinggemma-2:latest',digest)


def test_equivalent_duplicate_names_are_ambiguous_and_rejected():
    runtime=OllamaEmbedder('http://synthetic.invalid',ModelConfig(expected_digest='sha256:'+HASH),object())
    runtime._request=lambda *_:{'models':[{'name':'embeddinggemma-2','digest':HASH},{'name':'embeddinggemma-2:latest','digest':HASH}]}
    with pytest.raises(ModelError,match='MODEL_UNAVAILABLE'):runtime._digest()


def test_embed_response_bare_default_matches_explicit_latest_only():
    runtime=OllamaEmbedder('http://synthetic.invalid',ModelConfig(model_name='embeddinggemma-2:latest',expected_digest='sha256:'+HASH,vector_dimension=2),object())
    runtime._request=lambda *_:{'model':'embeddinggemma-2','embeddings':[[1,0]],'prompt_eval_count':3}
    assert runtime._vector('synthetic',3)==[1.0,0.0]


def test_embed_response_extra_tag_suffix_is_not_equivalent():
    runtime=OllamaEmbedder('http://synthetic.invalid',ModelConfig(model_name='embeddinggemma-2:approved',expected_digest='sha256:'+HASH,vector_dimension=2),object())
    runtime._request=lambda *_:{'model':'embeddinggemma-2:approved:latest','embeddings':[[1,0]],'prompt_eval_count':3}
    with pytest.raises(ModelError,match='MODEL_RESPONSE_IDENTITY_MISMATCH'):runtime._vector('synthetic',3)
