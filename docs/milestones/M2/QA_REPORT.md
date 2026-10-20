# M2 final independent QA checkpoint — 2026-10-20

**Latest: all reported code findings RESOLVED within executed local/mock scope. PENDING HUMAN APPROVAL; initial-profile TDD exception and external verification limits remain.** Historical FAIL observations below are retained as evidence and do not describe the corrected final code.

Independent QA m2_final_qa actually ran the expanded suite:177PASS/1 existing Starlette warning in13.98s, baseline DOC_STATIC_PASS and diffcheck. After identifying a Minor invalid port500, Main wrote a failing regression, fixed httpx.InvalidURL→ValueError, and QA independently ran that new case:1PASS/6 deselected in0.71s, sanitized422/zero registration/zero source calls. Main final fullsuite178PASS is separately recorded in TEST_REPORT.md.

| Round | Findings | Independent outcome |
|---|---|---|
|1 | OI-035 oversized429/401 ordering, OI-036 active permit expiry, OI-037 empty-response deadline |20 transport/migration tests PASS; macOS process/mock evidence |
|2 | OI-038 Item-local conversion stops good siblings; OI-039 unknown request cost; OI-040 scope identity; OI-041 normalized fields | Expanded regression and actual product-adapter failure-isolation controls PASS |
|3 | OI-042 equivalent default-port origins bypass budgets; OI-043 worker asset directory; OI-044 invalid port validation | Original aliases/path repro now corrected;177 full tests+new targeted1 PASS |

OI-042 original actual repro:429 Retry-After15 at1000 then equivalent :443 profile sends200 at1000, separate pause1015/0. Corrected original reproduction:only1 actual request, equivalent second profile hits RETRY_BUDGET_EXHAUSTED while paused, matching server keys/lock directories. HTTP default80 regression also passed. Old noncanonical budget state fails closed with SERVER_ORIGIN_MIGRATION_REQUIRED without state deletion. OI-043 configured path is now honored consistently. OI-044 now422 INVALID_REQUEST rather than500, zero writes/source requests.

No new Major remained in the final independent review. QA did not modify files. Frontend and container results below are Main-run evidence; no independent execution is claimed. Read GATE_MATRIX.md and the v0.2 controls for the M2-only assessment of TEST-044..059. The initial connection/config prototype lacks test-first chronology; later tests do not erase that TDD_NOT_EVIDENCED exception. User review is required.

NOT VERIFIED: real ALM/renderer/deletion/sockets, non-macOS process-lock matrix/shared filesystems, full UI/HTML safety and remote CI. Runtime/main evidence and detailed retained boundaries are in COMPLETION.md and TEST_REPORT.md. M2 approval belongs to the user; M3 has not started.

Final independent document reconciliation also PASS: machine-checked15 Primary+6 Shared match unchanged baseline assignments, no duplicate rows/missing references; TEST-044..059 correctly defer later gates. Main178 versus independent177+target1 and initial-prototype TDD_NOT_EVIDENCED are accurately distinguished. No new document blocker; scoped human review ready. This does not grant M2 approval or accept OI-045.

---

# Historical QA observations — 2026-10-20

Verdict: **FAIL — two Major, one Minor; Human Review required.** Reviewer: independent m2_transport_qa specialist (read-only). Main transport is uncommitted on codex/m2-collectors, after2a934c5. Reviewer did not modify implementation or contact live ALM servers.

| ID | Severity / requirement | Observed defect and expected boundary |
|---|---|---|
| OI-035 | Major / SRS-053,054 | alm_http.py request reads body before status handling.429 Retry-After15 with100-byte body/10-byte limit raises RESPONSE_TOO_LARGE(global_error=False); pause_until remains0; next call at1000.2 rather than>=1015. Classify protection headers before body limits and before permit release.401 bypass is inferred from the same code path, not separately reproduced. |
| OI-036 | Major / SRS-053,054 | _acquire lease expires at timeout_seconds+5 even if stream remains active. max_inflight1, timeout1, budget100, stream7seconds allows2 active streams. A per-read timeout does not bound request lifetime; active permits need a correct lifetime boundary. |
| OI-037 | Minor / SRS-053,054 | Deadline checked inside yielded chunks only. Budget1second, response returns empty200 after2seconds, still succeeds. Validate acquisition/header/completion boundaries. |

Existing tests: **10 passed** (transport9+migration1), independently executed; Main rerun10 passed in0.58s. These do not cover the counterexamples. Live server compatibility, real-socket timing and separate-process transport concurrency are **NOT VERIFIED**. Specialist connector/collection green tests have not been integrated or accepted as complete M2 QA.

## Exact independent reproduction

Executed by QA, exit0. Exit0 means the diagnostic script ran; printed observations demonstrate failures, not acceptance PASS. Temporary SQLite fixtures only. No project files changed.

```sh
.venv/bin/python - <<'PY'
from pathlib import Path
from tempfile import TemporaryDirectory
import httpx
from almrag.storage import Database
from almrag.alm_http import ALMHttpClient, HttpPolicy, AlmError
class Clock:
 def __init__(self): self.now=1000.
 def __call__(self): return self.now
 def sleep(self,s): self.now+=s
with TemporaryDirectory() as temp:
 db=Database(Path(temp)/'db.sqlite');db.migrate();uid=db.add_instance('codebeamer','https://alm.example.invalid','fixture','ref');clock=Clock()
 def make(handler,**kw): return ALMHttpClient(db,uid,'https://alm.example.invalid',transport=httpx.MockTransport(handler),clock=clock,sleep=clock.sleep,jitter=lambda:0,**kw)
 a=make(lambda req:httpx.Response(429,headers={'Retry-After':'15'},content=b'x'*100),policy=HttpPolicy(max_response_bytes=10))
 try:a.get_json('/v3/projects')
 except AlmError as e:print('OVERSIZED_429_ERROR',e.code,e.global_error)
 with db.connect() as c:print('OVERSIZED_429_PAUSE',c.execute('SELECT pause_until FROM server_budgets').fetchone()[0])
 b=make(lambda req:httpx.Response(200,json={}))
 b.get_json('/v3/projects');print('NEXT_REQUEST_TIME',clock())
with TemporaryDirectory() as temp:
 db=Database(Path(temp)/'db.sqlite');db.migrate();uid=db.add_instance('codebeamer','https://alm.example.invalid','fixture','ref');clock=Clock();active=[0];peak=[0];second=[None]
 class Stream(httpx.SyncByteStream):
  def __init__(self,outer):self.outer=outer;active[0]+=1;peak[0]=max(peak[0],active[0])
  def __iter__(self):
   if self.outer:
    clock.now+=7
    second[0].request('GET','/v3/projects')
   yield b'ok'
  def close(self):active[0]-=1
 def make(handler):return ALMHttpClient(db,uid,'https://alm.example.invalid',policy=HttpPolicy(requests_per_second=1000,burst=10,min_interval_ms=0,max_inflight=1,timeout_seconds=1,total_budget_seconds=100),transport=httpx.MockTransport(handler),clock=clock,sleep=clock.sleep)
 first=make(lambda req:httpx.Response(200,stream=Stream(True)));second[0]=make(lambda req:httpx.Response(200,stream=Stream(False)))
 first.request('GET','/v3/projects');print('MAX_INFLIGHT_POLICY_1_ACTUAL',peak[0])
with TemporaryDirectory() as temp:
 db=Database(Path(temp)/'db.sqlite');db.migrate();uid=db.add_instance('codebeamer','https://alm.example.invalid','fixture','ref');clock=Clock()
 def late_empty(req):clock.now+=2;return httpx.Response(200)
 a=ALMHttpClient(db,uid,'https://alm.example.invalid',policy=HttpPolicy(total_budget_seconds=1),transport=httpx.MockTransport(late_empty),clock=clock,sleep=clock.sleep)
 print('BUDGET_1_LATE_EMPTY_STATUS',a.request('GET','/v3/projects').status_code,'ELAPSED',clock()-1000)
PY
```

Actual QA output:

```text
OVERSIZED_429_ERROR RESPONSE_TOO_LARGE False
OVERSIZED_429_PAUSE 0.0
NEXT_REQUEST_TIME 1000.2
MAX_INFLIGHT_POLICY_1_ACTUAL 2
BUDGET_1_LATE_EMPTY_STATUS 200 ELAPSED 2.0
```

## Gate decision

AGENTS.md Milestone discipline: “On unresolved Critical/Major bugs, data loss, sensitive exposure, scope change to SRS/SAD, stop immediately and request human review.” Implementation stopped. Fixes have not been attempted and defects remain OPEN. Proposed corrective work is concrete in COMPLETION.md; user review is required before resumption. No claim of full M2 QA or repaired behavior is made.

## Subsequent approved correction and new integration gate

User approved OI-035/036/037 remediation with “수정안을 적용하고 계속진행해”. Specialist Transport corrections and independent revalidation are recorded below when completed; the initial observations above remain historical evidence.

**OI-038: Major / SRS-055 / OPEN.** Read-only collector specialist executed an actual two-Item Mock with CodebeamerConnector + CollectionService and temporary SQLite. First Item customFields is an object instead of a field list; second Item is valid. Valid source project/scope/catalog and complete pagination; no credentials/storage errors. Actual output:

```text
PREFLIGHT READY
RESULT BLOCKED
JOB {'state': 'BLOCKED', 'progress_total': 2, 'succeeded_items': 0, 'failed_items': 0, 'last_error_code': 'INVALID_SOURCE_PAYLOAD'}
ITEM_DETAIL_REQUESTS ['/v3/items/100']
FAILED_ITEM_RECORDS 0
SAVED_REVISIONS 0
SECOND_ITEM_VALID 101
```

Cause: get_item customFields normalization invokes _list, which raises ConnectorError(global_error=True); CollectionService stops globally. FAIL_SAFE_AND_REPLAY explicitly classifies Item field conversion as Item-local. Entire valid siblings remain unprocessed and the failed Item queue stays empty, so this is Major functionality failure, not data loss/Critical. New implementation paused pending Human Review; no correction to this error boundary attempted.

Additional non-Major findings: request estimates omit side calls (OI-039, synthetic1-item estimate6/observed8); tracker-local field-definition IDs lack scope in storage identity (OI-040); default normalized title/description versus numeric source catalog IDs blocks preflight (OI-041, Main integration2FAIL/3PASS). Actual source deletion evidence is NOT VERIFIED; no live server test occurred.

## Known transport correction independent verification — latest

**OI-035/036/037: PASS / RESOLVED within observed local scope.** After Main copied the frozen repair, independent QA executed `.venv/bin/python -m pytest tests/test_alm_http.py tests/test_m2_migrations.py -q`: **20 passed in1.34s**, no skips (19 transport+1 migration), macOS26.3.1 arm64/Python3.12.12.

Review confirmed401 credential block and429/5xx global pause persisted before body reads and before permit release; a regression inspects state inside release. OS slot ownership prevents expiry reclaim while stream is active; spawned-process active-owner, process-death recovery, canonical symlink alias and failed-commit cleanup tests passed. Acquisition/headers/empty completion/close boundaries reject expired deadlines. TRANSPORT_TDD.md records actual Red/Green.

Limits: only local macOS/fcntl filesystem exercised. Linux/Windows/msvcrt, shared filesystem lock semantics and real socket timing remain NOT VERIFIED. Logical deadline rejects late completion while retaining permit; hard interruption of a blocked synchronous socket read is not proven. Never delete/recreate stable lockfiles with workers active; all processes must share canonical database and lock directory. This is not M2 acceptance: new Major OI-038 remains OPEN; full suite3FAIL/132PASS, REST/client/contract work incomplete.
