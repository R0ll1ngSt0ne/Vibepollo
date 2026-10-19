import { defineConfig } from '@playwright/test';
import base from './playwright.config';

// Test the production UI with mocked APIs. No proxy to the installed host.
export default defineConfig({
  ...base,
  use: { ...base.use, baseURL: 'http://127.0.0.1:5174' },
  webServer: {
    command: 'npm run preview -- --host 127.0.0.1 --port 5174 --strictPort',
    url: 'http://127.0.0.1:5174/v2/',
    reuseExistingServer: false,
  },
});
