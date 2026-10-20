"""SRS-024: retired generations receive worker maintenance outside job leases."""
from almrag.worker import _ConfiguredCollection
from almrag.config import Settings


def test_cleanup_pending_uses_existing_index_and_preserves_retry_on_error(tmp_path):
    worker=_ConfiguredCollection(None,Settings(database_path=str(tmp_path/'db')))
    calls=[]
    class Index:
        def cleanup(self): calls.append('cleanup')
    worker.indexing=Index()
    worker.cleanup_pending()
    assert calls==['cleanup']


def test_cleanup_pending_before_first_job_is_lazy(tmp_path):
    worker=_ConfiguredCollection(None,Settings(database_path=str(tmp_path/'db')))
    worker.cleanup_pending()
    assert not hasattr(worker,'indexing')
