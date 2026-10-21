"""SRS-018/035/036/058: exact Item lookup work scales with that Item, not project points."""
import importlib.util
from pathlib import Path
from contextlib import contextmanager
from almrag.storage import Database,canonical_uid
from almrag.retrieval import SearchService

def test_exact_id_lookup_has_bounded_sqlite_work_across_large_project(tmp_path):
    spec=importlib.util.spec_from_file_location('bench',Path(__file__).parents[1]/'tools/benchmark_m6.py');bench=importlib.util.module_from_spec(spec);spec.loader.exec_module(bench)
    class Store:
        def ensure_collection(self,*args):pass
        def upsert(self,*args):pass
        def query(self,*args,**kwargs):return []
    db=Database(tmp_path/'db');db.migrate();runtime=bench.FixtureRuntime();store=Store()
    p,g,_=bench._seed(db,store,'almrag_fixture',2000,runtime)
    original=db.connect
    @contextmanager
    def bounded():
        with original() as c:
            ticks=[0]
            def progress():
                ticks[0]+=100
                return ticks[0]>10000
            c.set_progress_handler(progress,100)
            yield c
    db.connect=bounded
    search=SearchService(db,lambda _:runtime,store,allow_fixture=True,page_size=1,max_rounds=1)
    search.lexical.search=lambda *a,**kw:[]
    response=search.search({'query':'SYN-001999','project_uids':[p],'top_k':1},allowed_projects=[p])
    assert response['results'][0]['item_uid']==canonical_uid('item',p,'SYN-001999')
