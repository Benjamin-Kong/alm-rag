import { defineConfig } from '@playwright/test';
export default defineConfig({
  testDir:'./e2e', testMatch:'**/*.pw.ts', fullyParallel:false, workers:1,
  use:{baseURL:'http://127.0.0.1:4173',headless:true},
  webServer:[
    {command:'npm run dev -- --port 4173 --strictPort',url:'http://127.0.0.1:4173',reuseExistingServer:false},
    {command:'../.venv/bin/python ../tools/native_e2e_server.py',url:'https://127.0.0.1:19443/api/v1/healthz',ignoreHTTPSErrors:true,reuseExistingServer:false},
    {command:'../.venv/bin/python ../tools/intranet_browser_fixture.py',url:'http://127.0.0.1:19444/api/v1/healthz',reuseExistingServer:false},
  ],
  reporter:[['list']], timeout:30000,
});
