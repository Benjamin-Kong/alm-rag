// SRS-027/040: generated request types, credential headers and safe failures.
import { expect, test, vi } from 'vitest';
import { ApiClient } from './client';

test('encodes identifiers and uses same-origin typed requests', async () => {
  const fetcher = vi.fn().mockResolvedValue({ ok: true, status: 200, json: async () => [] });
  const client = new ApiClient({ apiKey: 'synthetic-key', csrf: 'synthetic-csrf' }, fetcher);
  await client.jobEvents('id/with space');
  expect(fetcher.mock.calls[0][0]).toBe('/api/v1/jobs/id%2Fwith%20space/events');
  await client.createKey({ name: 'reader', project_uids: ['p1'], permissions: ['project_read'] });
  const options = fetcher.mock.calls[1][1];
  expect(options.credentials).toBe('same-origin');
  expect(options.headers['X-API-Key']).toBe('synthetic-key');
  expect(options.headers['X-CSRF-Token']).toBe('synthetic-csrf');
});

test('never echoes error bodies or transport exceptions', async () => {
  const rejected = new ApiClient({}, vi.fn().mockResolvedValue({ ok: false, status: 403, json: async () => ({ secret: 'private-value' }) }));
  await expect(rejected.projects()).rejects.toThrow('Request failed (403)');
  const unavailable = new ApiClient({}, vi.fn().mockRejectedValue(new Error('private-value')));
  await expect(unavailable.projects()).rejects.toThrow('Service unavailable');
});

test('M2 discovery, source-specific policy and COLLECT use generated request types', async () => {
  const fetcher = vi.fn().mockResolvedValue({ ok: true, status: 202, json: async () => ({ job_id: 'job', state: 'QUEUED' }) });
  const client = new ApiClient({ csrf: 'synthetic-csrf' }, fetcher);
  await client.discoverProjects('source/id');
  expect(fetcher.mock.calls[0][0]).toBe('/api/v1/alm-instances/source%2Fid/projects');
  await client.configureCollection('project', {scope_kind: 'WORK_ITEM_TYPE', selection_mode: 'SELECTED', source_scope_ids: ['requirement'], embedding_fields: ['title']});
  expect(fetcher.mock.calls[1][1].method).toBe('PUT');
  await client.preflight('project');
  expect(fetcher.mock.calls[2][0]).toBe('/api/v1/projects/project/preflight');
  const job = await client.startJob('project', {stage: 'COLLECT', force: false, config_revision: 'observed'});
  expect(job.job_id).toBe('job');
  expect(JSON.parse(fetcher.mock.calls[3][1].body).stage).toBe('COLLECT');
});

test('M3 processing policy and preflight use encoded project and typed input', async () => {
  const fetcher = vi.fn().mockResolvedValue({ok:true,status:200,json:async()=>({status:'BLOCKED',process_ready:false})});
  const client = new ApiClient({csrf:'fixture'},fetcher);
  await client.configureProcessing('p/id',{fields:[{kind:'SOURCE',key:'title'}]});
  expect(fetcher.mock.calls[0][0]).toBe('/api/v1/projects/p%2Fid/processing-config');
  expect(JSON.parse(fetcher.mock.calls[0][1].body).fields[0].kind).toBe('SOURCE');
  await client.processingConfig('p/id');
  expect(fetcher.mock.calls[1][1].method).toBe('GET');
  const pre = await client.processingPreflight('p/id');
  expect(pre.process_ready).toBe(false);
  await client.configureProcessingDefaults('i/id',{fields:[]});
  expect(fetcher.mock.calls[3][0]).toBe('/api/v1/alm-instances/i%2Fid/processing-defaults');
});
