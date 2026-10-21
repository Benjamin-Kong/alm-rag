// SRS-044/045/058: actual browser Unicode-v form pattern must be valid.
import {expect,test} from 'vitest';
import {render,screen,cleanup} from '@testing-library/react';
import {Wizard} from './Wizard';
import type {ConsoleContext} from './App';
test('credential reference form pattern compiles with browser Unicode v flag',()=>{
 const ctx={principal:{admin_session:true},projects:[],client:{}} as unknown as ConsoleContext;
 render(<Wizard ctx={ctx}/>);
 try{
  const pattern=(screen.getByLabelText('자격증명 참조') as HTMLInputElement).pattern;
  const regexp=new RegExp('^(?:'+pattern+')$','v');
  expect(regexp.test('env:ALM_TOKEN')).toBe(true);expect(regexp.test('vault:my-token')).toBe(true);expect(regexp.test('raw-secret')).toBe(false);
 }finally{cleanup();}
});
