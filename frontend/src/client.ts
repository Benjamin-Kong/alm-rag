import type { components } from './generated-api';

type Schema = components['schemas'];
export class ApiRequestError extends Error {
  constructor(readonly status: number) { super(`Request failed (${status})`); }
}

/** Same-origin client; credentials live only in the caller's memory. */
export class ApiClient {
  constructor(
    private readonly credentials: { apiKey?: string; csrf?: string } = {},
    private readonly fetcher: typeof fetch = fetch,
    private readonly signal?: AbortSignal,
  ) {}

  private async request<T>(method: string, path: string, body?: unknown): Promise<T> {
    const headers: Record<string, string> = {};
    if (body !== undefined) headers['Content-Type'] = 'application/json';
    if (this.credentials.apiKey) headers['X-API-Key'] = this.credentials.apiKey;
    if (this.credentials.csrf && method !== 'GET') headers['X-CSRF-Token'] = this.credentials.csrf;
    try {
      const fetcher=this.fetcher;
      const response = await fetcher('/api/v1' + path, {
        method, headers, credentials: 'same-origin', signal: this.signal,
        body: body === undefined ? undefined : JSON.stringify(body),
      });
      if (!response.ok) throw new ApiRequestError(response.status);
      return response.status === 204 ? undefined as T : await response.json() as T;
    } catch (error) {
      if (error instanceof ApiRequestError) throw error;
      throw new Error('Service unavailable');
    }
  }

  me() { return this.request<Schema['PrincipalInfo']>('GET', '/auth/me'); }
  sources() { return this.request<Schema['InstanceDetail'][]>('GET', '/alm-instances'); }
  updateSource(source: string, input: Schema['CodebeamerProfile'] | Schema['PolarionProfile']) {
    return this.request<Schema['InstanceDetail']>('PUT', '/alm-instances/' + encodeURIComponent(source), input);
  }
  deleteSource(source: string) { return this.request<void>('DELETE', '/alm-instances/' + encodeURIComponent(source)); }
  items(project: string) { return this.request<Schema['ItemMetadata'][]>('GET', '/projects/' + encodeURIComponent(project) + '/items'); }
  revisions(item: string) { return this.request<Schema['RevisionInfo'][]>('GET', '/items/' + encodeURIComponent(item) + '/revisions'); }
  chunks(item: string) { return this.request<Schema['ChunkInfo'][]>('GET', '/items/' + encodeURIComponent(item) + '/chunks'); }
  diagnostics(job: string) { return this.request<Schema['DiagnosticInfo'][]>('GET', '/jobs/' + encodeURIComponent(job) + '/diagnostics'); }
  exportProject(project: string) { return this.request<Schema['JobInfo']>('POST', '/projects/' + encodeURIComponent(project) + '/export', {}); }
  importProject(project: string, input: Schema['ProjectImportRequest']) { return this.request<Schema['JobInfo']>('POST', '/projects/' + encodeURIComponent(project) + '/import', input); }
  artifacts(project: string) { return this.request<Schema['ArtifactInfo'][]>('GET', '/projects/' + encodeURIComponent(project) + '/artifacts'); }
  backups() { return this.request<Schema['ArtifactInfo'][]>('GET', '/backups'); }
  backup() { return this.request<Schema['ArtifactInfo']>('POST', '/backups', {}); }
  backupSchedule(input: Schema['BackupSchedule']) { return this.request<Schema['BackupSchedule']>('PUT', '/backups/schedule', input); }
  prepareRestore(id: string) { return this.request<Schema['RestorePreparation']>('POST', '/backups/' + encodeURIComponent(id) + '/prepare-restore', {}); }
  restore(id: string, input: Schema['BackupRestoreRequest']) { return this.request<Schema['RecoveryInfo']>('POST', '/backups/' + encodeURIComponent(id) + '/restore', input); }
  async stageArtifact(project: string, file: File) {
    const headers: Record<string,string> = {'Content-Type':'application/zip'};
    if (this.credentials.apiKey) headers['X-API-Key']=this.credentials.apiKey;
    if (this.credentials.csrf) headers['X-CSRF-Token']=this.credentials.csrf;
    const fetcher=this.fetcher;
    const response=await fetcher('/api/v1/projects/'+encodeURIComponent(project)+'/artifacts/stage',{method:'POST',headers,credentials:'same-origin',body:file,signal:this.signal});
    if(!response.ok) throw new ApiRequestError(response.status);
    return await response.json() as Schema['ArtifactInfo'];
  }
  async downloadArtifact(id: string) {
    const headers: Record<string,string> = {};
    if (this.credentials.apiKey) headers['X-API-Key']=this.credentials.apiKey;
    const fetcher=this.fetcher;
    const response=await fetcher('/api/v1/artifacts/'+encodeURIComponent(id)+'/download',{headers,credentials:'same-origin',signal:this.signal});
    if(!response.ok) throw new ApiRequestError(response.status);
    return response.blob();
  }
  stageEvaluation(project: string,input: Schema['GoldenDataset']) {return this.request<Schema['DatasetInfo']>('POST','/projects/'+encodeURIComponent(project)+'/evaluation-datasets',input);}
  evaluate(project: string,dataset: string,topK=10) {return this.request<Schema['JobInfo']>('POST','/projects/'+encodeURIComponent(project)+'/evaluations',{project_uids:[project],dataset_ref:dataset,methods:['dense','keyword','hybrid'],top_k:topK});}
  integrity(project: string) {return this.request<Schema['JobInfo']>('POST','/projects/'+encodeURIComponent(project)+'/integrity',{});}
  qualityReport(job: string) {return this.request<Schema['QualityReport']>('GET','/jobs/'+encodeURIComponent(job)+'/quality-report');}
  health() { return this.request<Schema['Health']>('GET', '/healthz'); }
  readiness() { return this.request<Schema['Health']>('GET', '/readyz'); }
  projects() { return this.request<Schema['ProjectInfo'][]>('GET', '/projects'); }
  jobs() { return this.request<Schema['JobInfo'][]>('GET', '/jobs'); }
  job(id: string) { return this.request<Schema['JobInfo']>('GET', '/jobs/' + encodeURIComponent(id)); }
  jobEvents(id: string) { return this.request<Schema['JobEvent'][]>('GET', '/jobs/' + encodeURIComponent(id) + '/events'); }
  login(input: Schema['Login']) { return this.request<void>('POST', '/auth/login', input); }
  logout() { return this.request<void>('POST', '/auth/logout'); }
  createKey(input: Schema['KeyCreate']) { return this.request<Schema['KeyCreated']>('POST', '/api-keys', input); }
  revokeKey(id: string) { return this.request<void>('DELETE', '/api-keys/' + encodeURIComponent(id)); }
  startJob(project: string, input: Schema['Stage']) {
    return this.request<Schema['JobInfo']>('POST', '/projects/' + encodeURIComponent(project) + '/jobs', input);
  }
  registerSource(input: Schema['CodebeamerProfile'] | Schema['PolarionProfile']) {
    return this.request<Schema['InstanceInfo']>('POST', '/alm-instances', input);
  }
  probeSource(source: string) {
    return this.request<Record<string, unknown>>('POST', '/alm-instances/' + encodeURIComponent(source) + '/probe');
  }
  discoverProjects(source: string) {
    return this.request<Schema['SourceProject'][]>('GET', '/alm-instances/' + encodeURIComponent(source) + '/projects');
  }
  discoverScopes(source: string, project: string) {
    return this.request<Schema['SourceScope'][]>('GET', '/alm-instances/' + encodeURIComponent(source) + '/projects/' + encodeURIComponent(project) + '/scopes');
  }
  discoverFields(source: string, project: string, scopeIds: string[]) {
    const query = scopeIds.map((id) => 'scope_ids=' + encodeURIComponent(id)).join('&');
    return this.request<Record<string, unknown>[]>('GET', '/alm-instances/' + encodeURIComponent(source) + '/projects/' + encodeURIComponent(project) + '/fields?' + query);
  }
  setRatePolicy(source: string, input: Schema['HttpPolicy']) {
    return this.request<Schema['HttpPolicy']>('PUT', '/alm-instances/' + encodeURIComponent(source) + '/rate-policy', input);
  }
  registerProject(input: Schema['ProjectCreate']) { return this.request<Schema['ProjectInfo']>('POST', '/projects', input); }
  configureCollection(project: string, input: Schema['CollectionConfig']) {
    return this.request<Schema['ProjectInfo']>('PUT', '/projects/' + encodeURIComponent(project) + '/collection-config', input);
  }
  preflight(project: string) { return this.request<Schema['PreflightInfo']>('POST', '/projects/' + encodeURIComponent(project) + '/preflight'); }
  processingConfig(project: string) {
    return this.request<Schema['ProcessingConfigInfo']>('GET', '/projects/' + encodeURIComponent(project) + '/processing-config');
  }
  configureProcessing(project: string, input: Schema['ProcessingPolicy']) {
    return this.request<Schema['ProcessingConfigInfo']>('PUT', '/projects/' + encodeURIComponent(project) + '/processing-config', input);
  }
  processingPreflight(project: string) {
    return this.request<Schema['ProcessingPreflightInfo']>('POST', '/projects/' + encodeURIComponent(project) + '/processing-preflight');
  }
  configureProcessingDefaults(source: string, input: Schema['ProcessingPolicy']) {
    return this.request<Schema['ProcessingDefaultsInfo']>('PUT', '/alm-instances/' + encodeURIComponent(source) + '/processing-defaults', input);
  }
  search(input: Schema['SearchRequest']) {
    return this.request<Schema['SearchResponse']>('POST', '/search', input);
  }
  itemDetail(item: string) {
    return this.request<Schema['ItemDetail']>('GET', '/items/' + encodeURIComponent(item));
  }
  indexPreflight(project: string, stage: 'INDEX' | 'REBUILD_INDEX' = 'INDEX') {
    return this.request<Schema['IndexPreflightInfo']>('POST', '/projects/' + encodeURIComponent(project) + '/index-preflight?stage=' + encodeURIComponent(stage));
  }
  pipelinePreflight(project: string) {
    return this.request<Schema['PipelinePreflightInfo']>('POST', '/projects/' + encodeURIComponent(project) + '/pipeline-preflight');
  }
  failedItems(job: string, pagination: { limit?: number; offset?: number } = {}) {
    const query = new URLSearchParams();
    if (pagination.limit !== undefined) query.set('limit', String(pagination.limit));
    if (pagination.offset !== undefined) query.set('offset', String(pagination.offset));
    const suffix = query.size ? '?' + query.toString() : '';
    return this.request<Schema['FailedItemInfo'][]>('GET', '/jobs/' + encodeURIComponent(job) + '/failed-items' + suffix);
  }
  retryItem(job: string, item: string, input: Schema['RetryItemRequest'] = {}) {
    return this.request<Schema['JobInfo']>('POST', '/jobs/' + encodeURIComponent(job) + '/failed-items/' + encodeURIComponent(item) + '/retry', input);
  }
  retryFailedItems(job: string, input: Schema['RetryItemRequest'] = {}) {
    return this.request<Schema['JobInfo'][]>('POST', '/jobs/' + encodeURIComponent(job) + '/failed-items/retry', input);
  }
  pauseJob(job: string) {
    return this.request<Schema['JobInfo']>('POST', '/jobs/' + encodeURIComponent(job) + '/pause');
  }
  resumeJob(job: string) {
    return this.request<Schema['JobInfo']>('POST', '/jobs/' + encodeURIComponent(job) + '/resume');
  }
  sync(project: string, configRevision?: string) { return configRevision ? this.startJob(project,{stage:'SYNC',config_revision:configRevision}) : this.request<Schema['JobInfo']>('POST', '/projects/' + encodeURIComponent(project) + '/sync'); }
  audit() { return this.request<Record<string, unknown>[]>('GET', '/audit-events'); }
}
