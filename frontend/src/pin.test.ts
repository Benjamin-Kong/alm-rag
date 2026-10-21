// SRS-047: execute exactly the configuration that passed preview.
import { expect,test,vi } from 'vitest';
import { ApiClient } from './client';
test('pinned SYNC uses the guarded stage endpoint and config revision',async()=>{
 const fetcher=vi.fn(async(_path:RequestInfo|URL,_init?:RequestInit)=>({ok:true,status:202,json:async()=>({job_id:'j'})} as Response));
 await new ApiClient({},fetcher as typeof fetch).sync('p','approved-config');
 expect(fetcher.mock.calls[0][0]).toBe('/api/v1/projects/p/jobs');
 expect(JSON.parse(fetcher.mock.calls[0][1]!.body as string)).toEqual({stage:'SYNC',config_revision:'approved-config'});
});
