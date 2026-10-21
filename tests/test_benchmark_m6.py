"""SRS-035/036: measured synthetic capacity, safe owned fixture and P95."""
import importlib.util
from pathlib import Path
import pytest


def load(name):
    spec=importlib.util.spec_from_file_location(name,Path(__file__).parents[1]/'tools'/f'{name}.py')
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module);return module


def test_nearest_rank_rejects_fabricated_empty_samples():
    bench=load('benchmark_m6')
    assert bench.nearest_rank([4,1,3,2],.95)==4
    with pytest.raises(ValueError):bench.nearest_rank([],.95)
    with pytest.raises(ValueError):bench.nearest_rank([float('nan')],.95)


def test_fixture_multiple_chunks_canonical_publications_and_cleanup(tmp_path):
    bench=load('benchmark_m6')
    class Store:
        def __init__(self):self.points={};self.deleted=[]
        def ensure_collection(self,name,dimension):self.name=name
        def upsert(self,name,points):self.points.update({p['id']:p for p in points})
        def delete_collection(self,name):self.deleted.append(name)
        def _request(self,method,path,payload):return {'count':len(self.points)}
        def query(self,name,vector,**kw):
            rows=[{'id':p['id'],'payload':p['payload'],'score':1.0} for p in self.points.values()]
            return rows[kw['offset']:kw['offset']+kw['limit']]
    store=Store()
    report=bench.run_benchmark(store,item_count=12,samples=3,warmups=1)
    assert report['capacity']['items']==12
    assert report['capacity']['chunks']==24
    assert report['capacity']['average_chunks_per_item']==2
    assert report['search']['samples']==3 and report['search']['top_k']==10
    assert report['search']['returned_items']==[10,10,10]
    assert report['actual_ollama_target']['status']=='NOT VERIFIED'
    assert report['production_pipeline']['status']=='NOT VERIFIED'
    assert report['status_scope']=='SYNTHETIC_CAPACITY_AND_RETRIEVAL_FUNCTIONALITY'
    assert report['search']['latency_status'] in ('PASS','FAIL')
    assert report['fixture_seeding']['is_collector_embedding_throughput'] is False
    assert store.deleted==[store.name]
    with pytest.raises(ValueError):bench.run_benchmark(store,item_count=True)


def test_embedding_measurement_changed_ratio_failure_and_environment():
    bench=load('benchmark_embedding')
    ticks=iter([10.,12.])
    calls=[]
    def embed(batch):
        calls.append(batch)
        if 'bad' in batch:raise ValueError('synthetic failure')
        return [[1.,0.] for _ in batch]
    report=bench.measure_embedding(embed,['aa','bbb','bad','dddd'],token_counter=len,batch_size=2,changed_ratio=.75,environment='CPU',clock=lambda:next(ticks))
    assert report['attempted_chunks']==3 and report['successful_chunks']==2 and report['failed_chunks']==1
    assert report['successful_tokens']==5 and report['chunks_per_second']==1
    assert report['tokens_per_second']==2.5 and report['environment']=='CPU'
    assert calls==[['aa','bbb'],['bad']]
    with pytest.raises(ValueError):bench.measure_embedding(embed,['x'],token_counter=len,changed_ratio=1.1)
