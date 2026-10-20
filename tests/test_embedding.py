"""SRS-015/017/048: digest/tokenizer-bound Ollama embeddings, synthetic only."""
import hashlib
import json
import httpx
import pytest
from almrag.embedding import ModelConfig, ModelError, OllamaEmbedder, LocalTokenizer

DIGEST='sha256:'+'a'*64

class FixtureTokenizer:
    identity='fixture-codepoint-v1'
    def count(self,text):return len(text)


def backend(*,digest=DIGEST,count_delta=0,vector=None,status=200):
    calls=[]
    def handle(request):
        calls.append(request)
        if request.url.path=='/api/tags':return httpx.Response(200,json={'models':[{'name':'embeddinggemma-2:latest','digest':digest}]})
        if request.url.path=='/api/show':return httpx.Response(200,json={'capabilities':['embedding'],'model_info':{'gemma4.context_length':8192}})
        assert request.url.path=='/api/embed' and request.method=='POST'
        body=json.loads(request.content)
        assert body['truncate'] is False and isinstance(body['input'],str)
        return httpx.Response(status,json={'model':'embeddinggemma-2:latest','embeddings':[vector if vector is not None else [1.0,0.0,0.0]],'prompt_eval_count':len(body['input'])+count_delta})
    return calls,httpx.MockTransport(handle)


def config(**changes):
    return ModelConfig(model_name='embeddinggemma-2',expected_digest=DIGEST,vector_dimension=3,effective_max_input_tokens=128,**changes)


def test_runtime_probe_binds_digest_and_exact_count_without_truncation():
    calls,transport=backend()
    client=OllamaEmbedder('https://model.example.invalid',config(),FixtureTokenizer(),transport=transport,allow_fixture=True)
    profile=client.verify_runtime()
    assert profile['state']=='FIXTURE_ONLY' and profile['model_digest']==DIGEST
    assert profile['tokenizer_id']==FixtureTokenizer.identity
    assert client.embed('한글 test',expected_tokens=7)==[1.0,0.0,0.0]
    assert sum(r.url.path=='/api/embed' for r in calls)>=3


@pytest.mark.parametrize('changes,code',[(dict(digest='sha256:'+'b'*64),'MODEL_DIGEST_MISMATCH'),(dict(count_delta=-1),'TOKENIZER_MISMATCH'),(dict(vector=[1.0]),'VECTOR_INTEGRITY_ERROR')])
def test_runtime_mismatch_never_becomes_verified(changes,code):
    _,transport=backend(**changes)
    client=OllamaEmbedder('https://model.example.invalid',config(),FixtureTokenizer(),transport=transport,allow_fixture=True)
    with pytest.raises(ModelError,match=code):client.verify_runtime()
    assert client.profile is None


def test_no_network_or_fixture_trust_without_explicit_injection():
    client=OllamaEmbedder('https://model.example.invalid',config(),FixtureTokenizer())
    with pytest.raises(ModelError,match='MODEL_NETWORK_DISABLED'):client.verify_runtime()
    _,transport=backend()
    client=OllamaEmbedder('https://model.example.invalid',config(),FixtureTokenizer(),transport=transport)
    with pytest.raises(ModelError,match='TOKENIZER_UNVERIFIED'):client.verify_runtime()


def test_embedding_requires_verified_runtime_and_rejects_oversize():
    calls,transport=backend()
    client=OllamaEmbedder('https://model.example.invalid',config(),FixtureTokenizer(),transport=transport,allow_fixture=True)
    with pytest.raises(ModelError,match='MODEL_RUNTIME_UNVERIFIED'):client.embed('text',expected_tokens=4)
    client.verify_runtime();before=len(calls)
    with pytest.raises(ModelError,match='INPUT_TOO_LARGE'):client.embed('x'*129,expected_tokens=129)
    assert len(calls)==before


def test_local_tokenizer_uses_only_pinned_artifact_and_counts_special_tokens(tmp_path):
    from tokenizers import Tokenizer,models,pre_tokenizers,processors
    tokenizer=Tokenizer(models.WordLevel({'[UNK]':0,'[BOS]':1,'hello':2,'world':3},unk_token='[UNK]'))
    tokenizer.pre_tokenizer=pre_tokenizers.Whitespace()
    tokenizer.post_processor=processors.TemplateProcessing(single='[BOS] $A',special_tokens=[('[BOS]',1)])
    path=tmp_path/'tokenizer.json';tokenizer.save(str(path))
    digest=hashlib.sha256(path.read_bytes()).hexdigest()
    exact=LocalTokenizer(path,digest)
    assert exact.count('hello world')==3
    assert digest in exact.identity
    with pytest.raises(ModelError,match='TOKENIZER_ARTIFACT_MISMATCH'):LocalTokenizer(path,'0'*64)


def test_redirect_auth_and_nonfinite_vectors_are_sanitized():
    for status in [302,401,429]:
        client=OllamaEmbedder('https://model.example.invalid',config(),FixtureTokenizer(),transport=httpx.MockTransport(lambda _:httpx.Response(status,text='synthetic-sensitive')),allow_fixture=True)
        with pytest.raises(ModelError) as caught:client.verify_runtime()
        assert caught.value.global_error and 'synthetic-sensitive' not in str(caught.value)
    _,transport=backend(vector=[1,float('inf'),0])
    client=OllamaEmbedder('https://model.example.invalid',config(),FixtureTokenizer(),transport=transport,allow_fixture=True)
    with pytest.raises(ModelError):client.verify_runtime()


@pytest.mark.parametrize('mode',['truncation','padding'])
def test_local_tokenizer_counts_full_unpadded_input(tmp_path,mode):
    """SRS-013/048: artifact defaults cannot shorten or pad exact input counts."""
    from tokenizers import Tokenizer,models,pre_tokenizers
    tokenizer=Tokenizer(models.WordLevel({'[UNK]':0,'word':1,'[PAD]':2},unk_token='[UNK]'))
    tokenizer.pre_tokenizer=pre_tokenizers.Whitespace()
    if mode=='truncation':
        tokenizer.enable_truncation(max_length=8)
        text=' '.join(['word']*2000);expected=2000
    else:
        tokenizer.enable_padding(length=16,pad_id=2,pad_token='[PAD]')
        text='word';expected=1
    path=tmp_path/'tokenizer.json';tokenizer.save(str(path))
    exact=LocalTokenizer(path,hashlib.sha256(path.read_bytes()).hexdigest())
    assert exact.count(text)==expected


def test_pinned_tokenizer_chunks_long_input_without_artifact_truncation(tmp_path):
    """SRS-013/048/049: exact 15k-token source, special tokens and full span coverage."""
    from tokenizers import Tokenizer,models,pre_tokenizers,processors
    from almrag.chunking import ChunkConfig,make_chunks
    from almrag.normalization import normalize_field
    reference=Tokenizer(models.WordLevel({'[UNK]':0,'word':1,'[PAD]':2,'[BOS]':3},unk_token='[UNK]'))
    reference.pre_tokenizer=pre_tokenizers.Whitespace()
    reference.post_processor=processors.TemplateProcessing(single='[BOS] $A',special_tokens=[('[BOS]',3)])
    reference.enable_truncation(max_length=8)
    reference.enable_padding(length=16,pad_id=2,pad_token='[PAD]')
    path=tmp_path/'tokenizer.json';reference.save(str(path))
    checksum=hashlib.sha256(path.read_bytes()).hexdigest()
    exact=LocalTokenizer(path,checksum)
    reference.no_truncation();reference.no_padding()
    source=' '.join(['word']*15000)
    chunks=make_chunks(normalize_field(source),title='Title',field_id='normalized:description',tokenizer=exact,config=ChunkConfig(),model_fingerprint='synthetic')
    assert all(c['input_tokens']==len(reference.encode(c['input_text'],add_special_tokens=True).ids)<=1024 for c in chunks)
    assert len(chunks)>1
    assert exact.count(source)==15001  # Includes the preserved BOS token.
    assert exact.identity=='hf-json:'+checksum+':untruncated-unpadded-v1:special-tokens-on'
    covered=set()
    for chunk in chunks:
        for span in chunk['source_span_offsets']:
            covered.update(range(span['char_start'],span['char_end']))
    assert covered==set(range(len(source)))
    assert hashlib.sha256(path.read_bytes()).hexdigest()==checksum  # Source artifact is immutable.
