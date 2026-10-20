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
  ) {}

  private async request<T>(method: string, path: string, body?: unknown): Promise<T> {
    const headers: Record<string, string> = {};
    if (body !== undefined) headers['Content-Type'] = 'application/json';
    if (this.credentials.apiKey) headers['X-API-Key'] = this.credentials.apiKey;
    if (this.credentials.csrf && method !== 'GET') headers['X-CSRF-Token'] = this.credentials.csrf;
    try {
      const response = await this.fetcher('/api/v1' + path, {
        method, headers, credentials: 'same-origin',
        body: body === undefined ? undefined : JSON.stringify(body),
      });
      if (!response.ok) throw new ApiRequestError(response.status);
      return response.status === 204 ? undefined as T : await response.json() as T;
    } catch (error) {
      if (error instanceof ApiRequestError) throw error;
      throw new Error('Service unavailable');
    }
  }

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
  discoverFields(source: string, project: string) {
    return this.request<Record<string, unknown>[]>('GET', '/alm-instances/' + encodeURIComponent(source) + '/projects/' + encodeURIComponent(project) + '/fields');
  }
  setRatePolicy(source: string, input: Schema['HttpPolicy']) {
    return this.request<Schema['HttpPolicy']>('PUT', '/alm-instances/' + encodeURIComponent(source) + '/rate-policy', input);
  }
  registerProject(input: Schema['ProjectCreate']) { return this.request<Schema['ProjectInfo']>('POST', '/projects', input); }
  configureCollection(project: string, input: Schema['CollectionConfig']) {
    return this.request<Schema['ProjectInfo']>('PUT', '/projects/' + encodeURIComponent(project) + '/collection-config', input);
  }
  preflight(project: string) { return this.request<Schema['PreflightInfo']>('POST', '/projects/' + encodeURIComponent(project) + '/preflight'); }
  sync(project: string) { return this.request<never>('POST', '/projects/' + encodeURIComponent(project) + '/sync'); }
  audit() { return this.request<Record<string, unknown>[]>('GET', '/audit-events'); }
}
