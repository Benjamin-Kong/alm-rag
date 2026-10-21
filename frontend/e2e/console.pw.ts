import { test,expect,Page } from '@playwright/test';

async function mock(page:Page,admin=false) {
  const calls:{path:string,method:string,body:any}[]=[];
  await page.route('**/api/v1/**',async route=>{
    const req=route.request(),path=new URL(req.url()).pathname;let body:any=null;
    try{body=req.postDataJSON();}catch{}
    calls.push({path,method:req.method(),body});
    const value=path.endsWith('/healthz')?{status:'ok'}:path.endsWith('/auth/me')?{admin_session:admin,project_uids:['p'],permissions:admin?['system_admin','project_manage','project_read','search']:['project_read','search']}:
      path.endsWith('/projects')?[{project_uid:'p',alm_instance_uid:'s',source_project_id:'sp',name:'테스트 프로젝트'}]:
      path.endsWith('/jobs')&&req.method()==='GET'?[]:
      path.endsWith('/search')?{total:1,results:[{item_uid:'i',project_uid:'p',revision_uid:'r',title:'<img src=x onerror=alert(1)>',item:{title:'<script>window.__xss=1</script>',description:{raw:'<img src=x onerror="window.__xss=1">'}},matched_chunks:[]}],exhausted:true,backfill_limited:false,rounds:1,unindexed_project_uids:[]}:
      path.endsWith('/alm-instances')&&req.method()==='GET'?[]:
      path.endsWith('/backups')&&req.method()==='GET'?[]:[];
    await route.fulfill({status:200,json:value});
  });
  return calls;
}
async function connect(page:Page,projectName='테스트 프로젝트') {
  await page.goto('/');await page.getByLabel('API 키',{exact:true}).fill('synthetic-key');
  await page.getByRole('button',{name:'API 키로 연결',exact:true}).click();
  await expect(page.getByText(projectName,{exact:true}).first()).toBeVisible();
}

test('read-only scope disables source and stage changes and does not persist key',async({page})=>{
  await mock(page);await connect(page);
  await expect(page.getByRole('button',{name:'동기화 SYNC',exact:true})).toBeDisabled();
  await expect(page.getByRole('button',{name:'서버 등록',exact:true})).toBeDisabled();
  expect(await page.evaluate(()=>[localStorage.length,sessionStorage.length])).toEqual([0,0]);
  await expect(page.getByLabel('API 키',{exact:true})).toHaveCount(0);
  await expect(page.locator('body')).not.toContainText('synthetic-key');
  await page.screenshot({path:'/private/tmp/almrag-m5-dashboard.png',fullPage:true});
});

test('explicit project search escapes source HTML and forwards only checked scope',async({page})=>{
  const calls=await mock(page);await connect(page);
  await page.getByRole('button',{name:'검색 · Explorer',exact:true}).click();
  await page.getByLabel('검색어',{exact:true}).fill('SOME/IP-SD');
  await expect(page.getByRole('button',{name:'검색 실행',exact:true})).toBeDisabled();
  await page.getByRole('checkbox',{name:'테스트 프로젝트',exact:true}).check();
  await page.getByRole('button',{name:'검색 실행',exact:true}).click();
  await expect(page.getByText('<img src=x onerror=alert(1)>',{exact:true})).toBeVisible();
  await expect(page.locator('main img')).toHaveCount(0);
  expect(await page.evaluate(()=>Boolean((window as any).__xss))).toBe(false);
  expect(calls.find(c=>c.path.endsWith('/search'))?.body.project_uids).toEqual(['p']);
});

test('forbidden response renders sanitized error without server content',async({page})=>{
  await page.route('**/api/v1/**',route=>route.fulfill({status:403,json:{message:'private-server-secret'}}));
  await page.goto('/');await page.getByLabel('API 키',{exact:true}).fill('synthetic-key');
  await page.getByRole('button',{name:'API 키로 연결',exact:true}).click();
  await expect(page.getByRole('alert')).toContainText('권한');
  await expect(page.locator('body')).not.toContainText('private-server-secret');
});

for(const kind of ['codebeamer','polarion'] as const) {
 test(`${kind} wizard discovers product scopes and pins preflight before SYNC`,async({page})=>{
  await mock(page,true);const posts:{path:string,body:any}[]=[];
  await page.route('**/api/v1/alm-instances**',async route=>{
    const req=route.request(),path=new URL(req.url()).pathname;let body:any={};try{body=req.postDataJSON();}catch{}
    if(req.method()!=='GET')posts.push({path,body});
    const value=path.endsWith('/probe')?{status:'OK'}:path.endsWith('/scopes')?[{id:'t',name:'Requirements',kind:kind==='codebeamer'?'TRACKER':'WORK_ITEM_TYPE'}]:path.endsWith('/fields')?[{id:'cf',name:'Custom'}]:path.endsWith('/projects')?[{id:'source-p',name:'Source Project',url:'https://source.invalid/p'}]:path.endsWith('/rate-policy')?body:{instance_uid:'s',source_type:kind,display_name:'Server',base_url:'https://source.invalid',api_profile:kind==='codebeamer'?'cb-rest-v3':'polarion-rest-v1',auth_configured:true};
    await route.fulfill({status:path.endsWith('/alm-instances')?201:200,json:value});
  });
  await page.route('**/api/v1/projects**',async route=>{
    const req=route.request(),path=new URL(req.url()).pathname;let body:any={};try{body=req.postDataJSON();}catch{}
    if(req.method()!=='GET')posts.push({path,body});
    const info={project_uid:'p',alm_instance_uid:'s',source_project_id:'source-p',name:'Source Project'};
    const value=path.endsWith('/pipeline-preflight')?{status:'READY',sync_ready:true,config_revision:'pinned-preview',estimated_items:1,diagnostics:[]}:
      path.endsWith('/jobs')?{job_id:'j',project_uid:'p',stage:'SYNC',state:'QUEUED'}:path.endsWith('/processing-config')?{}:req.method()==='GET'?[info]:info;
    await route.fulfill({status:path.endsWith('/jobs')?202:path.endsWith('/projects')&&req.method()==='POST'?201:200,json:value});
  });
  await connect(page,'Source Project');await page.getByRole('button',{name:'서버 등록',exact:true}).click();
  await page.getByLabel('ALM 종류',{exact:true}).selectOption(kind);
  if(kind==='polarion')await expect(page.getByLabel('Codebeamer 인증 방식',{exact:true})).toHaveCount(0);
  await page.getByLabel('서버 표시명',{exact:true}).fill('Server');await page.getByLabel('서버 기본 URL',{exact:true}).fill('https://source.invalid');
  await page.getByLabel('자격증명 참조',{exact:true}).fill('env:FIXTURE');await page.getByRole('button',{name:'서버 저장 · 연결 검증',exact:true}).click();
  await page.getByLabel('원본 프로젝트',{exact:true}).selectOption('source-p');
  const label=kind==='codebeamer'?'Tracker':'Work Item Type';
  await page.getByRole('checkbox',{name:`모든 ${label} 수집`,exact:true}).uncheck();
  await page.getByRole('checkbox',{name:'Requirements (t)',exact:true}).check();
  await page.getByRole('checkbox',{name:'Custom · 원본 cf',exact:true}).check();
  await page.getByRole('button',{name:'프로젝트 · 정책 저장',exact:true}).click();
  await expect(page.getByRole('button',{name:'검증된 프로젝트 동기화',exact:true})).toBeDisabled();
  await page.getByRole('button',{name:'사전 검증 실행',exact:true}).click();
  await page.getByRole('button',{name:'검증된 프로젝트 동기화',exact:true}).click();
  await expect.poll(()=>posts.find(p=>p.path.endsWith('/jobs'))?.body).toEqual({stage:'SYNC',config_revision:'pinned-preview'});
  expect(posts.find(p=>p.path.endsWith('/projects'))?.body.scope_kind).toBe(kind==='codebeamer'?'TRACKER':'WORK_ITEM_TYPE');
  expect(posts.find(p=>p.path.endsWith('/projects'))?.body.source_scope_ids).toEqual(['t']);
  expect(posts.find(p=>p.path.endsWith('/alm-instances'))?.body.source_type).toBe(kind);
  await page.getByLabel('ALM 종류',{exact:true}).selectOption(kind==='codebeamer'?'polarion':'codebeamer');
  await expect(page.getByRole('button',{name:'검증된 프로젝트 동기화',exact:true})).toHaveCount(0);
 });
}

test('failure Explorer forwards stage-pinned retry and disables reader mutations',async({page})=>{
 await mock(page,true);const retries:any[]=[];
 await page.route('**/api/v1/jobs',route=>route.fulfill({json:[{job_id:'failed-job',project_uid:'p',stage:'SYNC',state:'COMPLETED_WITH_ERRORS'}]}));
 await page.route('**/api/v1/jobs/**',async route=>{
  const req=route.request(),path=new URL(req.url()).pathname;
  if(req.method()==='POST'){retries.push(req.postDataJSON());await route.fulfill({status:202,json:{job_id:'replay',project_uid:'p',stage:'REPLAY',state:'QUEUED'}});return;}
  await route.fulfill({json:path.endsWith('/failed-items')?[{failed_item_uid:'f',job_id:'failed-job',project_uid:'p',item_uid:'i',source_item_id:'REQ-7',revision_uid:'r',failed_stage:'EMBED',error_code:'INPUT_REJECTED',retryable:true,replay_state:'PENDING'}]:[]});
 });
 await connect(page);await page.getByRole('button',{name:'작업 · 실패 목록',exact:true}).click();
 await page.getByRole('button',{name:'failed-job',exact:true}).click();
 await page.getByRole('button',{name:'Item 재처리',exact:true}).click();
 await expect.poll(()=>retries.length).toBe(1);
 expect(retries[0]).toEqual({from_stage:'FAILED_STAGE',expected_revision_uid:'r'});
});

test('backup restore uses server preparation nonce and clears it after use',async({page})=>{
 await mock(page,true);let restored:any;
 const ref='00000000-0000-0000-0000-000000000001';
 await page.route('**/api/v1/backups**',async route=>{
  const req=route.request(),path=new URL(req.url()).pathname;
  if(path.endsWith('/prepare-restore')){await route.fulfill({json:{manifest_hash:'a'.repeat(64),confirmation_nonce:'b'.repeat(40),expires_at:9999999999,state:'RAW_ONLY_REBUILD_REQUIRED'}});return;}
  if(path.endsWith('/restore')){restored=req.postDataJSON();await route.fulfill({json:{recovery_ref:ref,state:'RAW_ONLY_REBUILD_REQUIRED',auth_state:'REREGISTRATION_REQUIRED'}});return;}
  await route.fulfill({json:[{artifact_ref:ref,project_uid:null,kind:'BACKUP',sha256:'a'.repeat(64),size:10,state:'RAW_ONLY_REBUILD_REQUIRED',created_at:1}]});
 });
 await connect(page);await page.getByRole('button',{name:'백업 · 패키지',exact:true}).click();
 await page.getByRole('button',{name:'백업 목록 조회',exact:true}).click();
 await page.getByLabel('복구할 백업',{exact:true}).selectOption(ref);
 await page.getByRole('button',{name:'복구 사전 검증',exact:true}).click();
 await page.getByRole('button',{name:'격리 복구 자료 생성',exact:true}).click();
 await expect.poll(()=>restored).toEqual({manifest_hash:'a'.repeat(64),confirmation_nonce:'b'.repeat(40)});
 await expect(page.getByRole('button',{name:'격리 복구 자료 생성',exact:true})).toHaveCount(0);
 await expect(page.locator('body')).not.toContainText('b'.repeat(40));
});

test('M6 golden dataset submits bound project and displays server metrics only',async({page})=>{
 const calls=await mock(page,true);
 await page.route('**/api/v1/projects/p/evaluation-datasets',async route=>{
  calls.push({path:new URL(route.request().url()).pathname,method:'POST',body:route.request().postDataJSON()});
  await route.fulfill({status:201,json:{dataset_ref:'gold',project_uid:'p',case_count:1,sha256:'a'.repeat(64)}});
 });
 await page.route('**/api/v1/projects/p/evaluations',async route=>{
  calls.push({path:new URL(route.request().url()).pathname,method:'POST',body:route.request().postDataJSON()});
  await route.fulfill({status:202,json:{job_id:'quality-job',project_uid:'p',stage:'EVALUATE',state:'QUEUED'}});
 });
 await page.route('**/api/v1/jobs/quality-job/quality-report',route=>route.fulfill({status:200,json:{job_id:'quality-job',project_uid:'p',stage:'EVALUATE',status:'PASS',report:{methods:{hybrid:{precision_at_k:0.1,recall_at_k:1,mrr:1}}}}}));
 await connect(page);await page.getByRole('button',{name:'검색 평가',exact:true}).click();
 await expect(page.getByRole('button',{name:'세 검색 방식 평가',exact:true})).toBeDisabled();
 await page.getByLabel('평가 검색어',{exact:true}).fill('SOME/IP-SD');
 await page.getByLabel('정답 Item UID (한 줄에 하나)',{exact:true}).fill('canonical-item');
 await page.getByRole('button',{name:'골든셋 저장',exact:true}).click();
 await expect(page.getByText(/검증된 골든셋/)).toBeVisible();
 await page.getByRole('button',{name:'세 검색 방식 평가',exact:true}).click();
 await expect(page.getByLabel('보고서 작업 ID',{exact:true})).toHaveValue('quality-job');
 await page.getByRole('button',{name:'보고서 조회',exact:true}).click();
 await expect(page.getByText(/precision_at_k/)).toBeVisible();
 expect(calls.find(c=>c.path.endsWith('/evaluations'))?.body).toEqual({project_uids:['p'],dataset_ref:'gold',methods:['dense','keyword','hybrid'],top_k:10});
 await page.getByLabel('평가 검색어',{exact:true}).fill('changed');
 await expect(page.getByRole('button',{name:'세 검색 방식 평가',exact:true})).toBeDisabled();
});

test('M6 read-only scope cannot create quality jobs',async({page})=>{
 await mock(page);await connect(page);await page.getByRole('button',{name:'검색 평가',exact:true}).click();
 await expect(page.getByRole('button',{name:'무결성 검사',exact:true})).toBeDisabled();
 await expect(page.getByRole('button',{name:'골든셋 저장',exact:true})).toBeDisabled();
});
