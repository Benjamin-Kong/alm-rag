import { defineConfig } from '@playwright/test';
export default defineConfig({
  testDir:'./e2e', testMatch:'**/*.pw.ts', fullyParallel:false, workers:1,
  use:{baseURL:'http://127.0.0.1:4173',headless:true},
  webServer:{command:'npm run dev -- --port 4173 --strictPort',url:'http://127.0.0.1:4173',reuseExistingServer:false},
  reporter:[['list']], timeout:30000,
});
