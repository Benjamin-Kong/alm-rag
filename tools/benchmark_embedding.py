"""SRS-037 injectable measurement harness. Never connects to a model implicitly."""
import math
import time


def measure_embedding(embed_batch,texts,*,token_counter,batch_size=1,changed_ratio=1.,environment='FIXTURE',clock=time.perf_counter):
    if type(batch_size) is not int or not 1<=batch_size<=1000 or isinstance(changed_ratio,bool) or not isinstance(changed_ratio,(float,int)) or not math.isfinite(changed_ratio) or not 0<=changed_ratio<=1:
        raise ValueError('Invalid batch or changed ratio')
    if environment not in ('CPU','GPU','REMOTE','FIXTURE') or not isinstance(texts,list) or any(not isinstance(t,str) or not t for t in texts):raise ValueError('Invalid measurement inputs')
    selected=texts[:math.ceil(len(texts)*changed_ratio)]
    tokens=[token_counter(t) for t in selected]
    if any(type(n) is not int or n<=0 for n in tokens):raise ValueError('Invalid token count')
    successful=successful_tokens=failed=0
    started=clock()
    for offset in range(0,len(selected),batch_size):
        batch=selected[offset:offset+batch_size]
        try:
            vectors=embed_batch(batch)
            if not isinstance(vectors,list) or len(vectors)!=len(batch) or any(not isinstance(v,list) or not v or any(isinstance(n,bool) or not isinstance(n,(int,float)) or not math.isfinite(n) for n in v) or not any(v) for v in vectors):raise ValueError('Invalid embedding result')
        except Exception:
            failed+=len(batch)
        else:
            successful+=len(batch);successful_tokens+=sum(tokens[offset:offset+len(batch)])
    elapsed=clock()-started
    if not math.isfinite(elapsed) or elapsed<=0:raise ValueError('Clock must advance')
    return dict(environment=environment,batch_size=batch_size,changed_ratio=changed_ratio,total_chunks=len(texts),attempted_chunks=len(selected),successful_chunks=successful,failed_chunks=failed,successful_tokens=successful_tokens,elapsed_seconds=elapsed,chunks_per_second=successful/elapsed,tokens_per_second=successful_tokens/elapsed)
