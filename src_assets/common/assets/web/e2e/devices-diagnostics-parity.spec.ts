import { join } from 'node:path';
import { tmpdir } from 'node:os';
import { localRoute, expect, test, type Page } from './fixtures';

const screenshotDirectory = process.env.VIBEPOLLO_TEST_OUTPUT || process.env.VIBESHINE_TEST_OUTPUT || join(tmpdir(), 'vibepollo-ui-results');

type FixtureOptions = {
  steamAccountsUnavailable?: boolean;
  policyFails?: boolean;
  assignmentFails?: boolean;
  deferred?: boolean;
  savedManagement?: boolean;
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
  await page.emulateMedia({ colorScheme: 'dark' });
  const platform = options.platform ?? 'windows';
  const calls = { policies: [] as Record<string, unknown>[], accounts: 0, vigem: 0, updates: [] as Record<string, unknown>[] };

  const assignments = new Map<string, string>();
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
      const patch = request.postDataJSON();
      if (!options.policyFails && typeof patch.steam_account_management === 'boolean') {
        options.savedManagement = patch.steam_account_management;
        if (!options.deferred) { options.steamManagement = patch.steam_account_management; options.migrationPending = false; }
      }
      body = { status: !options.policyFails, deferred: options.deferred ?? false };
    } else if (path === '/api/config') {
      body = {
        status: true,
        ...(options.migrationPending ? {} : { steam_account_management: String(options.savedManagement ?? options.steamManagement ?? true) }),
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
      body = { status: true, platform, named_certs: devices.map((device) => ({ ...device, steam_account_id: assignments.get(device.uuid) ?? options.steamAssignment ?? '' })) };
    } else if (path === '/api/steam/status') {
      body = { enabled: false, available: options.steamAvailable ?? true, companion: { supported: platform === 'windows', available: options.steamAvailable ?? true, account_management: options.steamManagement ?? true, resolution_automation: false, migration_pending: options.migrationPending ?? false } };
    } else if (path === '/api/clients/steam-accounts') {
      calls.accounts++;
      body = options.steamAccountsUnavailable ? { status: 'unavailable', accounts: [] } : {
        status: 'available', accounts: [{ steam_id: '76561197960265729', account_name: 'fixture-login', persona_name: 'Friendly <name>' }],
      };
    } else if (path === '/api/clients/update') {
      const update = request.postDataJSON();
      calls.updates.push(update);
      if (!options.assignmentFails) assignments.set(update.uuid, update.steam_account_id);
      body = { status: !options.assignmentFails };
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

test('Steam account list failure preserves assignment until a successful retry', async ({ page }) => {
  const fixture = { steamAccountsUnavailable: true, steamAssignment: '76561197960265730' };
  const calls = await installFixture(page, fixture);
  await page.goto('/v2/integrations');
  const assignment = page.locator('#steam-assignment-alpha');
  await expect(page.getByText(/Steam accounts could not be loaded/)).toBeVisible();
  await expect(assignment).toHaveValue('76561197960265730');
  await expect(assignment.locator('option:checked')).toHaveText('Saved account (name unavailable)');
  expect(calls.updates).toHaveLength(0);
  await expect(assignment).toBeDisabled();
  fixture.steamAccountsUnavailable = false;
  await page.getByRole('button', { name: 'Retry', exact: true }).click();
  await expect(assignment).toBeEnabled();
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
    await expect(page.getByRole('checkbox', { name: 'Manage Steam accounts for streaming', exact: true })).toBeChecked();
    await expect(page.getByRole('button', { name: /Keep account management/ })).toHaveCount(0);
    await expect(page.locator('#steam-assignment-alpha')).toHaveValue('76561197960265730');
  }
  expect(calls.accounts).toBe(0);
  expect(calls.updates).toHaveLength(0);
});

test('Steam automation opt-ins are independent and report deferred application', async ({ page }) => {
  const calls = await installFixture(page, { steamManagement: false, deferred: true });
  await page.goto('/v2/integrations');
  await page.getByRole('checkbox', { name: 'Manage Steam accounts for streaming', exact: true }).check();
  await expect.poll(() => calls.policies.length).toBe(1);
  expect(calls.policies[0]).toEqual({ steam_account_management: true });
  await expect(page.getByText(/Currently disabled · Enable pending/)).toBeVisible();
  await page.getByRole('checkbox', { name: 'Adjust supported games to stream resolution', exact: true }).check();
  await expect.poll(() => calls.policies.length).toBe(2);
  expect(calls.policies[1]).toEqual({ steam_resolution_automation: true });
  expect(calls.accounts).toBe(0);
  expect(calls.updates).toHaveLength(0);
});

test('device editor has no Steam management link and does not fetch accounts', async ({ page }) => {
  const calls = await installFixture(page);
  await page.goto('/v2/devices');
  await page.locator('#device-search').fill('Living');
  await page.getByRole('button', { name: 'Edit device' }).click();
  await expect(page.getByRole('link', { name: 'Manage Steam account assignments in Integrations' })).toHaveCount(0);
  expect(calls.accounts).toBe(0);
  await expect(page.locator('#client-alpha-steam-account')).toHaveCount(0);
  await page.locator('.client-settings-section--identity').screenshot({ path: join(screenshotDirectory, 'steam-implemented-pairing.png') });
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

test('Steam reload retains names and unsaved selections across errors and stale assignments', async ({ page }) => {
  const fixture: FixtureOptions = { steamAssignment: '76561197960265729' };
  const calls = await installFixture(page, fixture);
  await page.goto('/v2/integrations');
  const section = page.locator('#steam-streaming');
  const assignment = page.locator('#steam-assignment-alpha');
  await expect(assignment.locator('option:checked')).toHaveText('Friendly <name> (fixture-login)');
  await section.screenshot({ path: join(screenshotDirectory, 'steam-implemented-loaded.png') });
  await assignment.selectOption('');
  fixture.steamAssignment = '76561197960265730';
  await section.getByRole('button', { name: 'Reload accounts', exact: true }).click();
  await expect(assignment).toHaveValue('');
  await expect(section.getByText('Saved assignment changed. Your unsaved selection is retained.')).toBeVisible();
  fixture.steamAccountsUnavailable = true;
  await section.getByRole('button', { name: 'Reload accounts', exact: true }).click();
  await expect(section.getByRole('button', { name: 'Retry', exact: true })).toBeVisible();
  await expect(assignment.locator('option').filter({ hasText: 'Friendly <name> (fixture-login)' })).toHaveCount(1);
  await expect(assignment).toHaveValue('');
  await expect(assignment).toBeDisabled();
  await section.screenshot({ path: join(screenshotDirectory, 'steam-implemented-reload-error.png') });
  expect(calls.updates).toHaveLength(0);
});

test('Steam policy save failure reverts checkbox, never claims Saved, and legacy reload needs no extra action', async ({ page }) => {
  const fixture: FixtureOptions = { migrationPending: true, steamAssignment: '76561197960265729', policyFails: true, deferred: false };
  const calls = await installFixture(page, fixture);
  await page.goto('/v2/integrations');
  const section = page.locator('#steam-streaming');
  const checkbox = section.getByRole('checkbox', { name: 'Manage Steam accounts for streaming', exact: true });
  await expect(checkbox).toBeChecked();
  await expect(section.getByRole('button', { name: /Keep account management|Confirm enabled/ })).toHaveCount(0);
  await expect(section.getByText('Enabled · Saved', { exact: true })).toHaveCount(0);
  await page.reload();
  await expect(checkbox).toBeChecked();
  expect(calls.policies).toHaveLength(0);
  await checkbox.uncheck();
  await expect(checkbox).toBeChecked();
  await expect(section.getByText('Could not save. Account management is still enabled.')).toBeVisible();
  await expect(section.getByText('Enabled · Saved', { exact: true })).toHaveCount(0);
  await section.screenshot({ path: join(screenshotDirectory, 'steam-implemented-policy-failure.png') });
  fixture.policyFails = false;
  await checkbox.uncheck();
  await expect(section.getByText('Disabled · Saved', { exact: true })).toBeVisible();
  await expect(section.getByText(/Could not save/)).toHaveCount(0);
  await page.reload();
  await expect(checkbox).not.toBeChecked();
  await checkbox.check();
  await expect(page.locator('#steam-assignment-alpha')).toHaveValue('76561197960265729');
  await expect(section.getByText('Enabled · Saved', { exact: true })).toBeVisible();
});

test('Steam assignment save failure retains draft without success feedback and retry saves it', async ({ page }) => {
  const fixture: FixtureOptions = { assignmentFails: true };
  const calls = await installFixture(page, fixture);
  await page.goto('/v2/integrations');
  const assignment = page.locator('#steam-assignment-alpha');
  await expect(assignment).toBeEnabled();
  await expect(assignment.locator('option')).toHaveCount(2);
  await assignment.selectOption('76561197960265729');
  const row = assignment.locator('..');
  await row.getByRole('button', { name: 'Save assignment' }).click();
  await expect(row.getByText(/Your selection has not been saved/)).toBeVisible();
  await expect(row.getByText('Assignment saved.', { exact: true })).toHaveCount(0);
  await expect(assignment).toHaveValue('76561197960265729');
  fixture.assignmentFails = false;
  await row.getByRole('button', { name: 'Save assignment' }).click();
  await expect(row.getByText('Assignment saved.', { exact: true })).toBeVisible();
  await expect(row.getByRole('alert')).toHaveCount(0);
  await expect(row.getByRole('button', { name: 'Save assignment' })).toBeDisabled();
  expect(calls.updates).toHaveLength(2);
  await page.locator('#steam-streaming').screenshot({ path: join(screenshotDirectory, 'steam-implemented-assignment-saved.png') });
});

test('Steam delayed old reload cannot replace newer account results after disable and re-enable', async ({ page }) => {
  await installFixture(page, { deferred: false });
  let releaseOld!: () => void;
  const oldWait = new Promise<void>(resolve => { releaseOld = resolve; });
  let requests = 0;
  let oldFinished = false;
  await localRoute(page, '**/api/clients/steam-accounts', async route => {
    const request = ++requests;
    if (request === 1) await oldWait;
    await route.fulfill({ json: { status: 'available', accounts: [{ steam_id: '76561197960265729', account_name: 'fixture-login', persona_name: request === 1 ? 'Stale name' : 'Current name' }] } });
    if (request === 1) oldFinished = true;
  });
  await page.goto('/v2/integrations');
  const section = page.locator('#steam-streaming');
  await expect.poll(() => requests).toBe(1);
  await expect(section.getByRole('button', { name: 'Loading…', exact: true })).toBeDisabled();
  await section.screenshot({ path: join(screenshotDirectory, 'steam-implemented-loading.png') });
  const checkbox = section.getByRole('checkbox', { name: 'Manage Steam accounts for streaming', exact: true });
  await checkbox.uncheck();
  await expect(section.getByText('Disabled · Saved', { exact: true })).toBeVisible();
  await checkbox.check();
  await expect.poll(() => requests).toBe(2);
  const options = page.locator('#steam-assignment-alpha option');
  await expect(options.nth(1)).toHaveText('Current name (fixture-login)');
  releaseOld();
  await expect.poll(() => oldFinished).toBe(true);
  await page.evaluate(() => new Promise(requestAnimationFrame));
  await expect.poll(() => section.getByRole('button', { name: 'Reload accounts', exact: true }).count()).toBe(1);
  await expect(options.nth(1)).toHaveText('Current name (fixture-login)');
  await expect(options.filter({ hasText: 'Stale name' })).toHaveCount(0);
});

test('Steam successful empty and missing account results differ from first-load failure', async ({ page }) => {
  const fixture: FixtureOptions = { steamAssignment: '76561197960265730', steamAccountsUnavailable: true };
  await installFixture(page, fixture);
  await page.goto('/v2/integrations');
  const section = page.locator('#steam-streaming');
  const assignment = page.locator('#steam-assignment-alpha');
  await expect(assignment.locator('option:checked')).toHaveText('Saved account (name unavailable)');
  await section.screenshot({ path: join(screenshotDirectory, 'steam-implemented-first-load-error.png') });
  await localRoute(page, '**/api/clients/steam-accounts', route => route.fulfill({ json: { status: 'available', accounts: [] } }));
  await section.getByRole('button', { name: 'Retry', exact: true }).click();
  await expect(section.getByText('No remembered Steam accounts found.')).toBeVisible();
  await expect(assignment.locator('option:checked')).toHaveText('Saved account (not in account list)');
  await section.screenshot({ path: join(screenshotDirectory, 'steam-implemented-empty.png') });
});


test('Steam implemented full panel uses existing app styling', async ({ page }) => {
  await installFixture(page, { steamAssignment: '76561197960265729' });
  await page.goto('/v2/integrations');
  await expect(page.locator('#steam-assignment-alpha')).toBeVisible();
  await page.getByRole('button', { name: 'Dark', exact: true }).click();
  await page.locator('#steam-streaming').scrollIntoViewIfNeeded();
  const style = await page.evaluate(() => ({font: getComputedStyle(document.body).fontFamily, bg: getComputedStyle(document.body).backgroundColor, theme: document.documentElement.dataset.theme, sheets: [...document.styleSheets].map(s=>({href:s.href,rules:s.cssRules.length}))}));
  await test.info().attach('rendered-style', { body: JSON.stringify(style), contentType: 'application/json' });
  expect(style.font).toContain('Segoe UI');
  expect(style.bg).toBe('rgb(16, 18, 24)');
  await page.screenshot({ path: join(screenshotDirectory, 'steam-implemented-full-panel.png') });
  await page.locator('#steam-streaming').screenshot({ path: join(screenshotDirectory, 'steam-implemented-styled-panel.png') });
});


test('Steam failed policy change during initial load retains pending account results', async ({ page }) => {
  await installFixture(page, { policyFails: true, steamAssignment: '76561197960265729' });
  let release!: () => void;
  const pending = new Promise<void>(resolve => { release = resolve; });
  await localRoute(page, '**/api/clients/steam-accounts', async route => {
    await pending;
    await route.fulfill({ json: { status: 'available', accounts: [{ steam_id: '76561197960265729', account_name: 'fixture-login', persona_name: 'Friendly' }] } });
  });
  await page.goto('/v2/integrations');
  const section = page.locator('#steam-streaming');
  const assignment = page.locator('#steam-assignment-alpha');
  await expect(assignment).toBeDisabled();
  await expect(assignment.locator('option:checked')).toHaveText('Saved account (name unavailable)');
  const checkbox = section.getByRole('checkbox', { name: 'Manage Steam accounts for streaming', exact: true });
  await checkbox.uncheck();
  await expect(checkbox).toBeChecked();
  await expect(section.getByText('Could not save. Account management is still enabled.')).toBeVisible();
  release();
  await expect(assignment.locator('option:checked')).toHaveText('Friendly (fixture-login)');
  await expect(assignment).toBeEnabled();
  await expect(section.getByText('Enabled · Saved', { exact: true })).toHaveCount(0);
});

test('Steam rapid policy toggles wait for the parent status refresh to finish', async ({ page }) => {
  const fixture: FixtureOptions = { steamManagement: true };
  const calls = await installFixture(page, fixture);
  let release!: () => void;
  const pending = new Promise<void>(resolve => { release = resolve; });
  let held = false;
  await localRoute(page, '**/api/playnite/status', async route => {
    if (calls.policies.length === 1) { held = true; await pending; }
    await route.fallback();
  });
  await page.goto('/v2/integrations');
  const section = page.locator('#steam-streaming');
  const checkbox = section.getByRole('checkbox', { name: 'Manage Steam accounts for streaming', exact: true });
  await expect(checkbox).toBeEnabled();
  await checkbox.uncheck();
  await expect.poll(() => held).toBe(true);
  await expect(checkbox).toBeDisabled();
  const nextToggle = checkbox.check();
  expect(calls.policies).toHaveLength(1);
  release();
  await nextToggle;
  await expect.poll(() => calls.policies.length).toBe(2);
  await expect(checkbox).toBeEnabled();
  await expect(checkbox).toBeChecked();
  expect(fixture.steamManagement).toBe(true);
  await expect(section.getByText('Enabled · Saved', { exact: true })).toBeVisible();
});

test('Steam deferred policy shows effective protection and the saved choice separately', async ({ page }) => {
  const fixture: FixtureOptions = { steamManagement: true, deferred: true };
  const calls = await installFixture(page, fixture);
  await page.goto('/v2/integrations');
  const section = page.locator('#steam-streaming');
  const checkbox = section.getByRole('checkbox', { name: 'Manage Steam accounts for streaming', exact: true });
  await expect(checkbox).toBeEnabled();
  await checkbox.uncheck();
  await expect(checkbox).toBeEnabled();
  expect(fixture.savedManagement).toBe(false);
  expect(fixture.steamManagement).toBe(true);
  await expect(checkbox).not.toBeChecked();
  await expect(section.getByText('Currently enabled · Disable pending', { exact: true })).toBeVisible();
  await expect(section.getByText(/Currently enabled · Disable pending/)).toBeVisible();
  await page.getByRole('button', { name: 'Refresh status', exact: true }).click();
  await expect(checkbox).toBeEnabled();
  await expect(checkbox).not.toBeChecked();
  await expect(section.getByText(/Currently enabled · Disable pending/)).toBeVisible();
  await section.screenshot({ path: join(screenshotDirectory, 'steam-implemented-deferred-policy.png') });
  await page.reload();
  await expect(checkbox).toBeEnabled();
  await expect(checkbox).not.toBeChecked();
  await expect(section.getByText('Currently enabled · Disable pending', { exact: true })).toBeVisible();
  expect(calls.policies).toHaveLength(1);
  fixture.steamManagement = false; // Session ended: backend applies the persisted setting.
  await page.getByRole('button', { name: 'Refresh status', exact: true }).click();
  await expect(checkbox).toBeEnabled();
  await expect(section.getByText('Disabled · Saved', { exact: true })).toBeVisible();
  await expect(section.getByText(/Currently enabled · Disable pending/)).toHaveCount(0);
  expect(calls.policies).toHaveLength(1);
});

test('Steam saved policy with failed authoritative refresh reports verification failure', async ({ page }) => {
  const calls = await installFixture(page);
  let failStatus = true;
  await localRoute(page, '**/api/steam/status', async route => {
    if (calls.policies.length && failStatus) await route.fulfill({ status: 503, json: { status: false } });
    else await route.fallback();
  });
  await page.goto('/v2/integrations');
  const section = page.locator('#steam-streaming');
  const checkbox = section.getByRole('checkbox', { name: 'Manage Steam accounts for streaming', exact: true });
  await expect(checkbox).toBeEnabled();
  await checkbox.uncheck();
  await expect(section.getByText('The setting was saved, but current status could not be refreshed.')).toBeVisible();
  await expect(section.getByText('Current status unavailable', { exact: true })).toBeVisible();
  await expect(section.getByText('Disabled · Saved', { exact: true })).toHaveCount(0);
  failStatus = false;
  await page.getByRole('button', { name: 'Refresh status', exact: true }).click();
  await expect(checkbox).toBeEnabled();
  await expect(checkbox).not.toBeChecked();
  await expect(section.getByText('The setting was saved, but current status could not be refreshed.')).toHaveCount(0);
});

for (const changedStatus of [false, true]) for (const succeeds of [false, true])
test(`Steam pending assignment POST keeps ${succeeds ? 'success' : 'failure'} after parent refresh (${changedStatus ? 'changed' : 'same'} status)`, async ({ page }) => {
  const fixture: FixtureOptions = { assignmentFails: !succeeds };
  await installFixture(page, fixture);
  let release!: () => void;
  const pending = new Promise<void>(resolve => { release = resolve; });
  let started = false, clientLoads = 0;
  await localRoute(page, '**/api/clients/list', async route => { ++clientLoads; await route.fallback(); });
  await localRoute(page, '**/api/clients/update', async route => { started = true; await pending; await route.fallback(); });
  await page.goto('/v2/integrations');
  const assignment = page.locator('#steam-assignment-alpha');
  const row = assignment.locator('..');
  await expect(assignment).toBeEnabled();
  await assignment.selectOption('76561197960265729');
  await row.getByRole('button', { name: 'Save assignment' }).click();
  await expect.poll(() => started).toBe(true);
  const before = clientLoads;
  if (changedStatus) fixture.steamAvailable = false;
  const refresh = page.getByRole('button', { name: 'Refresh status', exact: true });
  await refresh.click();
  await expect(refresh).toBeEnabled();
  expect(clientLoads).toBe(before);
  release();
  if (changedStatus) await expect.poll(() => clientLoads).toBe(before + 1);
  await expect(assignment).toHaveValue('76561197960265729');
  if (succeeds) {
    await expect(row.getByText('Assignment saved.', { exact: true })).toBeVisible();
    await expect(row.getByRole('alert')).toHaveCount(0);
  } else {
    await expect(row.getByText(/Your selection has not been saved/)).toBeVisible();
    await expect(row.getByText('Assignment saved.', { exact: true })).toHaveCount(0);
  }
});


test('Steam failed change to a pending saved choice does not misreport effective protection', async ({ page }) => {
  const fixture: FixtureOptions = { steamManagement: true, deferred: true };
  await installFixture(page, fixture);
  await page.goto('/v2/integrations');
  const section = page.locator('#steam-streaming');
  const checkbox = section.getByRole('checkbox', { name: 'Manage Steam accounts for streaming', exact: true });
  await expect(checkbox).toBeEnabled();
  await checkbox.uncheck();
  await expect(checkbox).toBeEnabled();
  await expect(section.getByText(/Currently enabled · Disable pending/)).toBeVisible();
  fixture.policyFails = true;
  await checkbox.check();
  await expect(checkbox).not.toBeChecked();
  await expect(section.getByText('Could not save. The previous saved choice is unchanged.')).toBeVisible();
  await expect(section.getByText('Currently enabled · Disable pending', { exact: true })).toBeVisible();
  expect(fixture.savedManagement).toBe(false);
  expect(fixture.steamManagement).toBe(true);
});


test('Steam policy completion queues authoritative refresh behind a parent load started during PATCH', async ({ page }) => {
  const fixture: FixtureOptions = { steamManagement: true };
  const calls = await installFixture(page, fixture);
  let releasePatch!: () => void, releaseParent!: () => void;
  const patchPending = new Promise<void>(resolve => { releasePatch = resolve; });
  const parentPending = new Promise<void>(resolve => { releaseParent = resolve; });
  let patchStarted = false, parentHeld = false, statusReads = 0;
  await localRoute(page, '**/api/config', async route => {
    if (route.request().method() === 'PATCH') { patchStarted = true; await patchPending; }
    await route.fallback();
  });
  await localRoute(page, '**/api/steam/status', async route => { ++statusReads; await route.fallback(); });
  await localRoute(page, '**/api/playnite/status', async route => {
    if (patchStarted && !calls.policies.length) { parentHeld = true; await parentPending; }
    await route.fallback();
  });
  await page.goto('/v2/integrations');
  const section = page.locator('#steam-streaming');
  const checkbox = section.getByRole('checkbox', { name: 'Manage Steam accounts for streaming', exact: true });
  await expect(checkbox).toBeEnabled();
  const before = statusReads;
  await checkbox.uncheck();
  await expect.poll(() => patchStarted).toBe(true);
  await page.getByRole('button', { name: 'Refresh status', exact: true }).click();
  await expect.poll(() => parentHeld).toBe(true);
  releasePatch();
  await expect.poll(() => calls.policies.length).toBe(1);
  await expect(checkbox).toBeDisabled();
  releaseParent();
  await expect.poll(() => statusReads).toBe(before + 2);
  await expect(checkbox).toBeEnabled();
  await expect(checkbox).not.toBeChecked();
  await expect(section.getByText('Disabled · Saved', { exact: true })).toBeVisible();
  expect(fixture.steamManagement).toBe(false);
});

for (const effective of [false, true]) test(`Steam cancelling deferred choice reconciles unchanged effective ${effective}`, async ({ page }) => {
  const fixture: FixtureOptions = { steamManagement: effective, deferred: true };
  const calls = await installFixture(page, fixture);
  await page.goto('/v2/integrations');
  const section = page.locator('#steam-streaming');
  const checkbox = section.getByRole('checkbox', { name: 'Manage Steam accounts for streaming', exact: true });
  await expect(checkbox).toBeEnabled();
  await checkbox.setChecked(!effective);
  await expect(checkbox).toBeEnabled();
  await expect(section.getByText(effective ? 'Currently enabled · Disable pending' : 'Currently disabled · Enable pending', { exact: true })).toBeVisible();
  await checkbox.setChecked(effective);
  await expect(checkbox).toBeEnabled();
  await expect(section.getByText(/pending|Saved choice applies/)).toHaveCount(0);
  expect(fixture.savedManagement).toBe(effective);
  expect(fixture.steamManagement).toBe(effective);
  await page.getByRole('button', { name: 'Refresh status', exact: true }).click();
  await expect(checkbox).toBeEnabled();
  await expect(section.getByText(/pending|Saved choice applies/)).toHaveCount(0);
  await page.reload();
  await expect(checkbox).toBeEnabled();
  expect(await checkbox.isChecked()).toBe(effective);
  await expect(section.getByText(/pending|Saved choice applies/)).toHaveCount(0);
  expect(calls.policies).toHaveLength(2);
});

test('Steam persisted policy read failure never silently resets a pending saved choice', async ({ page }) => {
  const fixture: FixtureOptions = { steamManagement: true, savedManagement: false, deferred: true };
  const calls = await installFixture(page, fixture);
  let fail = false;
  await localRoute(page, '**/api/config', async route => {
    if (fail && route.request().method() === 'GET') await route.fulfill({status:503,json:{status:false}});
    else await route.fallback();
  });
  await page.goto('/v2/integrations');
  const section = page.locator('#steam-streaming');
  const checkbox = section.getByRole('checkbox', { name: 'Manage Steam accounts for streaming', exact: true });
  await expect(checkbox).toBeEnabled();
  await expect(checkbox).not.toBeChecked();
  await expect(section.getByText('Currently enabled · Disable pending', { exact: true })).toBeVisible();
  fail = true;
  await page.getByRole('button', { name: 'Refresh status', exact: true }).click();
  await expect(section.getByText('Current status unavailable', { exact: true })).toBeVisible();
  await expect(checkbox).toBeDisabled();
  await expect(checkbox).not.toBeChecked();
  await page.reload();
  await expect(section.getByText('Current status unavailable', { exact: true })).toBeVisible();
  await expect(checkbox).toBeDisabled();
  await expect(section.getByText(/Enabled · Saved|Disabled · Saved/)).toHaveCount(0);
  fail = false;
  await page.getByRole('button', { name: 'Refresh status', exact: true }).click();
  await expect(checkbox).toBeEnabled();
  await expect(checkbox).not.toBeChecked();
  await expect(section.getByText('Currently enabled · Disable pending', { exact: true })).toBeVisible();
  expect(calls.policies).toHaveLength(0);
});
