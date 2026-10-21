import {test,expect} from '@playwright/test';

test('explicit intranet HTTP browser authenticates session, enforces CSRF and runs actual worker report',async({browser})=>{
 const context=await browser.newContext({});
 const page=await context.newPage();
 try{
  await page.goto('http://127.0.0.1:19444/');
  await page.getByText('관리자 세션으로 연결',{exact:true}).click();
  await page.getByLabel('관리자 이름',{exact:true}).fill('synthetic-http-admin');
  await page.getByLabel('관리자 비밀번호',{exact:true}).fill('synthetic browser password');
  await page.getByRole('button',{name:'관리자 로그인',exact:true}).click();
  await expect(page.getByText('HTTP browser fixture',{exact:true})).toBeVisible();
  const cookies=await context.cookies();const session=cookies.find(c=>c.name==='almrag_session');
  expect(session?.secure).toBe(false);expect(session?.httpOnly).toBe(true);
  const projects=await (await context.request.get('http://127.0.0.1:19444/api/v1/projects')).json();const project=projects[0].project_uid;
  const rejected=await context.request.post('http://127.0.0.1:19444/api/v1/projects/'+project+'/integrity',{data:{}});
  expect(rejected.status()).toBe(403);
  await page.getByRole('button',{name:'검색 평가',exact:true}).click();
  await page.getByRole('button',{name:'무결성 검사',exact:true}).click();
  const input=page.getByLabel('보고서 작업 ID',{exact:true});await expect(input).not.toHaveValue('');
  const id=await input.inputValue();
  await expect.poll(async()=>{const response=await context.request.get('http://127.0.0.1:19444/api/v1/jobs/'+id);return (await response.json()).state;}).toBe('SUCCEEDED');
  await page.getByRole('button',{name:'보고서 조회',exact:true}).click();
  await expect(page.getByText(/LIVE_ALM_COMPLETENESS/)).toBeVisible();
  await expect(page.getByText(/NOT VERIFIED/)).toBeVisible();
  expect(await page.evaluate(()=>localStorage.length+sessionStorage.length)).toBe(0);
  await page.getByRole('button',{name:'연결 해제',exact:true}).click();
  await expect(page.getByRole('button',{name:'API 키로 연결',exact:true})).toBeVisible();
  expect((await context.request.get('http://127.0.0.1:19444/api/v1/projects')).status()).toBe(401);
 }finally{await context.close();}
});
