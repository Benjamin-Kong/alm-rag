import {test,expect} from '@playwright/test';
const base='https://127.0.0.1:19443';
async function adminLogin(page:import('@playwright/test').Page) {
 await page.goto(base+'/');
 await page.getByText('관리자 세션으로 연결',{exact:true}).click();
 await page.getByLabel('관리자 이름',{exact:true}).fill('synthetic-admin');
 await page.getByLabel('관리자 비밀번호',{exact:true}).fill('synthetic browser password');
 await page.getByRole('button',{name:'관리자 로그인',exact:true}).click();
 await expect(page.getByText('Native HTTPS fixture',{exact:true})).toBeVisible();
}
test('admin issues a search key, key user is restricted, admin revokes it',async({browser})=>{
 const context=await browser.newContext({ignoreHTTPSErrors:true,permissions:['clipboard-read','clipboard-write']});
 const page=await context.newPage();let raw='';
 try{
  await adminLogin(page);
  await page.getByRole('button',{name:'API Key 관리',exact:true}).click();
  await page.getByRole('button',{name:'+ 새 API Key 발급'}).click();
  const form=page.getByRole('region',{name:'새 API Key 발급'});
  await form.getByLabel('Name',{exact:true}).fill('e2e-search');
  await form.getByLabel('Native HTTPS fixture').check();
  await form.getByRole('button',{name:'API Key 생성'}).click();
  const dialog=page.getByRole('dialog',{name:'API Key 생성 완료'});
  await dialog.getByRole('button',{name:'API Key 복사'}).click();
  raw=await page.evaluate(()=>navigator.clipboard.readText());expect(raw.length).toBeGreaterThan(20);
  await dialog.getByRole('button',{name:'확인'}).click();
  await expect(page.getByText(raw)).toHaveCount(0);
  await expect(page.getByRole('cell',{name:'e2e-search',exact:true})).toBeVisible();
  expect(await page.evaluate(()=>localStorage.length+sessionStorage.length)).toBe(0);
  await page.getByRole('button',{name:'연결 해제',exact:true}).click();

  await page.getByLabel('API 키',{exact:true}).fill(raw);
  await page.getByRole('button',{name:'API 키로 연결',exact:true}).click();
  await expect(page.getByText('Native HTTPS fixture',{exact:true}).first()).toBeVisible();
  await expect(page.getByRole('button',{name:'API Key 관리',exact:true})).toHaveCount(0);
  await page.getByRole('button',{name:'검색 · Explorer',exact:true}).click();
  await page.getByLabel('Native HTTPS fixture').check();
  await page.getByLabel('검색어',{exact:true}).fill('fixture');
  await page.getByRole('button',{name:'검색 실행',exact:true}).click();
  await expect(page.getByRole('alert')).toHaveCount(0);
  expect((await context.request.get(base+'/api/v1/api-keys',{headers:{'X-API-Key':raw}})).status()).toBe(403);
  await page.getByRole('button',{name:'연결 해제',exact:true}).click();

  await adminLogin(page);
  await page.getByRole('button',{name:'API Key 관리',exact:true}).click();
  await page.getByRole('button',{name:'e2e-search 폐기'}).click();
  await page.getByRole('button',{name:'폐기 확인'}).click();
  await expect(page.getByRole('status').filter({hasText:'폐기했습니다'})).toBeVisible();
  await expect(page.getByRole('cell',{name:'Revoked',exact:true})).toBeVisible();
  expect((await context.request.get(base+'/api/v1/auth/me',{headers:{'X-API-Key':raw}})).status()).toBe(401);
 }finally{await context.close();}
});
