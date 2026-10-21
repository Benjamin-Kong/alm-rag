import {expect,test} from 'vitest';
import {ApiClient} from './client';
test('native-compatible fetch is called without binding it to the ApiClient object',async()=>{
 const fetcher=async function(this:unknown,_input:RequestInfo|URL,_init?:RequestInit){
  if(this!==undefined)throw new TypeError('Illegal invocation');
  return {ok:true,status:200,json:async()=>({admin_session:false,permissions:[],project_uids:[]})} as Response;
 };
 expect(await new ApiClient({},fetcher as typeof fetch).me()).toEqual({admin_session:false,permissions:[],project_uids:[]});
});
