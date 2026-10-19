import { join } from 'node:path';
import { tmpdir } from 'node:os';
import { localRoute, expect, test, type Page } from './fixtures';

const screenshotDirectory = process.env.VIBEPOLLO_TEST_OUTPUT || process.env.VIBESHINE_TEST_OUTPUT || join(tmpdir(), 'vibepollo-ui-results');

type FixtureOptions = {
  steamAccountsUnavailable?: boolean;
  steamManagement?: boolean;
  steamAvailable?: boolean;
  migrationPending?: boolean;
  steamAssignment?: string;
  platform?: 'windows' | 'linux' | 'macos';
  vigem?:
    | { status?: unknown; installed?: unknown; required?: unknown; version?: string }
    | 'error'
    | 'status-false'
    | 'malformed';
  controller?: unknown;
};

const devices = [
  {
    uuid: 'alpha',
    name: 'Living room',
    enabled: true,
    connected: true,
    last_seen: 1_788_955_190,
    display_mode: '1920x1080x60',
    hdr_profile: 'Living HDR',
    output_name_override: 'HDMI-A-1',
  },
  {
    uuid: 'beta',
    name: 'Bedroom',
    enabled: true,
    connected: false,
    last_seen: 1_788_955_000,
    display_mode: '2560x1440x60',
    hdr_profile: 'Bedroom HDR',
    virtual_display_mode: 'per_client',
  },
  {
    uuid: 'blocked-connected',
    name: 'Blocked pad',
    enabled: false,
    connected: true,
    last_seen: 1_788_955_100,
    display_mode: '1280x720x60',
  },
  {
    uuid: 'unnamed',
    name: null,
    enabled: true,
    connected: false,
    last_seen: null,
  },
];

async function installFixture(page: Page, options: FixtureOptions = {}) {
  const platform = options.platform ?? 'windows';
  const calls = { policies: [] as Record<string, unknown>[], accounts: 0, vigem: 0, updates: [] as Record<string, unknown>[] };

  await localRoute(page, '**/api/**', async (route) => {
    const request = route.request();
    const url = new URL(request.url());
    const path = url.pathname;
    if (!path.startsWith('/api/')) {
      await route.fallback();
      return;
    }

    let body: unknown = { status: true };
    if (path === '/api/auth/status') {
      body = { authenticated: true, login_required: false, credentials_configured: true };
    } else if (path === '/api/configLocale') {
      body = { locale: 'en' };
    } else if (path === '/api/csrf-token') {
      body = { csrf_token: 'fixture-token' };
    } else if (path === '/api/config' && request.method() === 'PATCH') {
      calls.policies.push(request.postDataJSON());
      body = { status: true, deferred: true };
    } else if (path === '/api/config') {
      body = {
        status: true,
        controller: options.controller ?? 'enabled',
        capture: 'wgc',
        virtual_display_mode: 'per_client',
        virtual_display_layout: 'exclusive',
      };
    } else if (path === '/api/metadata') {
      if (options.steamAccountsUnavailable) await new Promise(resolve => setTimeout(resolve, 150));
      body = {
        status: true,
        platform,
        version: 'fixture',
        providers: { steam: true },
        encoder_status: { state: 'ready', h264: true },
        capture_status: {
          configured_backend: 'kms',
          observed_backend: 'kms',
          managed_event_driven: true,
          virtual_display_configured: true,
        },
        virtual_display: { capable: true, ready: true },
      };
    } else if (path === '/api/session/status') {
      body = { status: true, activeSessions: 0, appRunning: false };
    } else if (path === '/api/host/stats') {
      body = {
        cpu_percent: 20,
        gpu_percent: 30,
        ram_percent: 40,
        vram_percent: 50,
        ram_used_bytes: 1,
        ram_total_bytes: 2,
        vram_used_bytes: 1,
        vram_total_bytes: 2,
      };
    } else if (path === '/api/host/info') {
      body = { cpu_model: 'Fixture CPU', gpu_model: 'Fixture GPU' };
    } else if (path === '/api/health/vigem') {
      calls.vigem += 1;
      if (options.vigem === 'error') {
        await route.fulfill({ status: 503, json: { error: 'diagnostic unavailable' } });
        return;
      }
      if (options.vigem === 'status-false') {
        body = { status: false, installed: false, version: '1.16.0' };
      } else if (options.vigem === 'malformed') {
        body = { status: true, installed: 'false', version: '1.16.0' };
      } else {
        body = options.vigem ?? { installed: true, version: '1.21.442.0' };
      }
    } else if (path === '/api/clients/list') {
      body = { status: true, platform, named_certs: devices.map((device) => ({ ...device, steam_account_id: options.steamAssignment ?? '' })) };
    } else if (path === '/api/steam/status') {
      body = { enabled: false, available: options.steamAvailable ?? true, companion: { supported: platform === 'windows', available: options.steamAvailable ?? true, account_management: options.steamManagement ?? true, resolution_automation: false, migration_pending: options.migrationPending ?? false } };
    } else if (path === '/api/clients/steam-accounts') {
      calls.accounts++;
      body = options.steamAccountsUnavailable ? { status: 'unavailable', accounts: [] } : {
        status: 'available', accounts: [{ steam_id: '76561197960265729', account_name: 'fixture-login', persona_name: 'Friendly <name>' }],
      };
    } else if (path === '/api/clients/update') {
      calls.updates.push(request.postDataJSON());
    } else if (path === '/api/clients/hdr-profiles') {
      body = { status: true, profiles: [] };
    } else if (path === '/api/display-devices') {
      body = [{ device_id: 'HDMI-A-1', friendly_name: 'Living room monitor' }];
    } else if (path === '/api/clients/display-layout') {
      body = { version: 1, placements: {} };
    } else if (path === '/api/apps') {
      body = { apps: [] };
    }
    await route.fulfill({ json: body });
  });

  return calls;
}

test('Steam assignment lives in Integrations and preserves identifier text', async ({ page }) => {
  const calls = await installFixture(page);
  await page.goto('/v2/integrations');
  const assignment = page.locator('#steam-assignment-alpha');
  await expect(assignment).toBeVisible();
  await expect(assignment.locator('option').nth(1)).toHaveText('Friendly <name> (fixture-login)');
  await assignment.selectOption('76561197960265729');
  await assignment.locator('..').getByRole('button', { name: 'Save assignment' }).click();
  await expect.poll(() => calls.updates.length).toBe(1);
  expect(calls.updates[0]).toEqual({ uuid: 'alpha', steam_account_id: '76561197960265729' });
});

test('Steam account list failure preserves assignment until explicitly cleared', async ({ page }) => {
  const calls = await installFixture(page, { steamAccountsUnavailable: true, steamAssignment: '76561197960265730' });
  await page.goto('/v2/integrations');
  const assignment = page.locator('#steam-assignment-alpha');
  await expect(page.getByText(/Accounts could not be refreshed/)).toBeVisible();
  await expect(assignment).toHaveValue('76561197960265730');
  await expect(assignment.locator('option:checked')).toHaveText('Previously assigned account (not currently listed)');
  expect(calls.updates).toHaveLength(0);
  await assignment.selectOption('');
  await assignment.locator('..').getByRole('button', { name: 'Save assignment' }).click();
  await expect.poll(() => calls.updates.length).toBe(1);
  expect(calls.updates[0].steam_account_id).toBe('');
});

for (const scenario of [
  { name: 'disabled', steamManagement: false },
  { name: 'absent installation', steamAvailable: false, migrationPending: true, steamAssignment: '76561197960265730' },
  { name: 'unsupported platform', platform: 'linux' as const },
]) test(`Steam ${scenario.name} does not fetch remembered accounts`, async ({ page }) => {
  const calls = await installFixture(page, scenario);
  await page.goto('/v2/integrations');
  await expect(page.getByRole('heading', { name: 'Steam streaming automation' })).toBeVisible();
  if (scenario.name === 'absent installation') {
    await expect(page.getByText(/Existing assignments were retained/)).toBeVisible();
    await expect(page.locator('#steam-assignment-alpha')).toHaveValue('76561197960265730');
  }
  expect(calls.accounts).toBe(0);
  expect(calls.updates).toHaveLength(0);
});

test('Steam automation opt-ins are independent and report deferred application', async ({ page }) => {
  const calls = await installFixture(page, { steamManagement: false });
  await page.goto('/v2/integrations');
  await page.getByRole('checkbox', { name: 'Manage Steam accounts for streaming', exact: true }).check();
  await expect.poll(() => calls.policies.length).toBe(1);
  expect(calls.policies[0]).toEqual({ steam_account_management: true });
  await expect(page.getByText(/Changes take effect after the active session/)).toBeVisible();
  await page.getByRole('checkbox', { name: 'Adjust supported games to stream resolution', exact: true }).check();
  await expect.poll(() => calls.policies.length).toBe(2);
  expect(calls.policies[1]).toEqual({ steam_resolution_automation: true });
  expect(calls.accounts).toBe(0);
  expect(calls.updates).toHaveLength(0);
});

test('device editor links to enabled management without fetching accounts', async ({ page }) => {
  const calls = await installFixture(page);
  await page.goto('/v2/devices');
  await page.locator('#device-search').fill('Living');
  await page.getByRole('button', { name: 'Edit device' }).click();
  await expect(page.getByRole('link', { name: 'Manage Steam account assignments in Integrations' })).toBeVisible();
  expect(calls.accounts).toBe(0);
  await expect(page.locator('#client-alpha-steam-account')).toHaveCount(0);
});

test('device filters search display metadata, sort deterministically, and keep drafts hidden by filters', async ({
  page,
}) => {
  await installFixture(page, { platform: 'linux' });
  await page.goto('/v2/devices');
  await expect(page.getByRole('heading', { name: 'Devices', exact: true })).toBeVisible();
  await expect(page.getByText('Search devices', { exact: true })).toBeVisible();
  await expect(page.locator('#device-status option[value="all"]')).toHaveText('All devices');
  await expect(page.locator('.device-row')).toHaveCount(4);

  // Recent keeps connected clients first and then uses last_seen descending.
  await expect(page.locator('.device-row h2').nth(0)).toHaveText('Living room');
  await expect(page.locator('.device-row h2').nth(1)).toHaveText('Blocked pad');

  await page.locator('#device-status').selectOption('connected');
  await expect(page.locator('.device-row')).toHaveCount(2);
  await expect(page.locator('.device-row h2').allTextContents()).resolves.toEqual([
    'Living room',
    'Blocked pad',
  ]);

  // Search covers UUID and display/HDR/routing metadata, not just the name.
  await page.locator('#device-status').selectOption('all');
  await page.locator('#device-search').fill('Bedroom HDR');
  await expect(page.locator('.device-row h2')).toHaveText('Bedroom');
  await page.locator('#device-search').fill('HDMI-A-1');
  await expect(page.locator('.device-row h2')).toHaveText('Living room');

  await page.locator('#device-search').fill('Living');
  await page.getByRole('button', { name: 'Edit device' }).click();
  await page.locator('#client-alpha-name').fill('Draft living room');
  await page.locator('#device-search').fill('');
  await page.locator('#device-status').selectOption('offline');
  await expect(page.locator('.device-row')).toHaveCount(2);
  await page.getByRole('button', { name: 'Clear filters' }).click();
  await expect(page.locator('#client-alpha-name')).toHaveValue('Draft living room');

  await page.locator('#device-sort').selectOption('status');
  await expect(page.locator('.device-row h2').allTextContents()).resolves.toEqual([
    'Blocked pad',
    'Living room',
    'Bedroom',
    'Unknown Client',
  ]);
  await page.locator('#device-sort').selectOption('name');
  await expect(page.locator('.device-row h2').allTextContents()).resolves.toEqual([
    'Bedroom',
    'Blocked pad',
    'Living room',
    'Unknown Client',
  ]);
  await page.screenshot({
    path: join(screenshotDirectory, 'devices-filters-desktop.png'),
    animations: 'disabled',
    fullPage: false,
  });
  await page.setViewportSize({ width: 390, height: 1000 });
  await page.screenshot({
    path: join(screenshotDirectory, 'devices-filters-mobile.png'),
    animations: 'disabled',
    fullPage: false,
  });
});

test('Windows overview reports only an explicit missing ViGEm driver with version and link', async ({
  page,
}) => {
  const calls = await installFixture(page, {
    platform: 'windows',
    vigem: { installed: false, version: '1.16.0' },
  });
  await page.goto('/v2/');
  await expect(page.getByText('Virtual Gamepad Driver (ViGEm) not installed')).toBeVisible();
  await expect(page.getByText(/Detected: 1\.16\.0/)).toBeVisible();
  await expect(page.getByRole('link', { name: 'Download ViGEmBus' })).toHaveAttribute(
    'href',
    'https://github.com/nefarius/ViGEmBus/releases/latest',
  );
  expect(calls.vigem).toBeGreaterThan(0);
  await page.screenshot({
    path: join(screenshotDirectory, 'overview-vigem-desktop.png'),
    animations: 'disabled',
    fullPage: false,
  });
  await page.setViewportSize({ width: 390, height: 1000 });
  await page.screenshot({
    path: join(screenshotDirectory, 'overview-vigem-mobile.png'),
    animations: 'disabled',
    fullPage: false,
  });
});

test('Linux overview never probes or displays the Windows ViGEm diagnostic', async ({ page }) => {
  const calls = await installFixture(page, {
    platform: 'linux',
    vigem: { installed: false, version: '1.16.0' },
  });
  await page.goto('/v2/');
  await expect(page.getByRole('heading', { name: 'Ready to stream', exact: true })).toBeVisible();
  await expect(page.getByText('Virtual Gamepad Driver (ViGEm) not installed')).toHaveCount(0);
  expect(calls.vigem).toBe(0);
});

test('Windows overview hides the ViGEm warning when the Vibepollo driver covers it', async ({
  page,
}) => {
  const calls = await installFixture(page, {
    platform: 'windows',
    vigem: { installed: false, required: false },
  });
  await page.goto('/v2/');
  await expect(page.getByRole('heading', { name: 'Ready to stream', exact: true })).toBeVisible();
  await expect(page.getByText('Virtual Gamepad Driver (ViGEm) not installed')).toHaveCount(0);
  expect(calls.vigem).toBeGreaterThan(0);
});

test('ViGEm diagnostic failure remains silent and controller false strings disable the probe', async ({
  page,
}) => {
  const failed = await installFixture(page, { platform: 'windows', vigem: 'error' });
  await page.goto('/v2/');
  await expect(page.getByRole('heading', { name: 'Ready to stream', exact: true })).toBeVisible();
  await expect(page.getByText('Virtual Gamepad Driver (ViGEm) not installed')).toHaveCount(0);
  expect(failed.vigem).toBeGreaterThan(0);

  const statusFalse = await installFixture(page, {
    platform: 'windows',
    vigem: 'status-false',
  });
  await page.goto('/v2/');
  await expect(page.getByRole('heading', { name: 'Ready to stream', exact: true })).toBeVisible();
  await expect(page.getByText('Virtual Gamepad Driver (ViGEm) not installed')).toHaveCount(0);
  expect(statusFalse.vigem).toBeGreaterThan(0);

  const malformed = await installFixture(page, { platform: 'windows', vigem: 'malformed' });
  await page.goto('/v2/');
  await expect(page.getByRole('heading', { name: 'Ready to stream', exact: true })).toBeVisible();
  await expect(page.getByText('Virtual Gamepad Driver (ViGEm) not installed')).toHaveCount(0);
  expect(malformed.vigem).toBeGreaterThan(0);

  const disabled = await installFixture(page, { platform: 'windows', controller: 'false' });
  await page.goto('/v2/');
  await expect(page.getByText('Virtual Gamepad Driver (ViGEm) not installed')).toHaveCount(0);
  expect(disabled.vigem).toBe(0);
});
