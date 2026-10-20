import assert from 'node:assert/strict';
import test from 'node:test';
import { parseRememberedSteamAccounts, steamAccountOptions } from '../utils/steamAccounts.ts';

const id = (BigInt('76561197960265728') + 1n).toString();
const row = { steam_id: id, account_name: 'fixture-login', persona_name: 'Friendly <name>' };
test('account dropdown uses names, preserves assignment and projects only allowed fields', () => {
  const accounts = parseRememberedSteamAccounts({ status: 'available', accounts: [{ ...row, unexpected: 'discard-me' }] });
  assert.deepEqual(accounts, [row]);
  assert.deepEqual(steamAccountOptions(accounts, id), [
    { value: '', label: 'Keep current account' },
    { value: id, label: 'Friendly <name> (fixture-login)' },
  ]);
  assert.equal(steamAccountOptions([], id)[1].value, id);
  assert.match(steamAccountOptions([], id)[1].label, /not currently listed/);
  assert.equal(steamAccountOptions([{ ...row, persona_name: '' }], id)[1].label, 'fixture-login');
});
test('unavailable, duplicate, imprecise numeric and malformed lists cannot replace an assignment', () => {
  for (const data of [null, { status: 'unavailable', accounts: [] },
    { status: 'available', accounts: [row, row] },
    { status: 'available', accounts: [{ ...row, steam_id: Number(id) }] },
    { status: 'available', accounts: [{ ...row, account_name: 'bad\nname' }] },
    { status: 'available', accounts: [{ ...row, persona_name: 'x'.repeat(129) }] }])
    assert.throws(() => parseRememberedSteamAccounts(data));
});
