import assert from 'node:assert/strict';
import test from 'node:test';
import { parseRememberedSteamAccounts, steamAccountOptions, parseSavedSteamManagement } from '../utils/steamAccounts.ts';

const id = (BigInt('76561197960265728') + 1n).toString();
const row = { steam_id: id, account_name: 'fixture-login', persona_name: 'Friendly <name>' };
test('account dropdown uses names, preserves assignment and projects only allowed fields', () => {
  const accounts = parseRememberedSteamAccounts({ status: 'available', accounts: [{ ...row, unexpected: 'discard-me' }] });
  assert.deepEqual(accounts, [row]);
  assert.deepEqual(steamAccountOptions(accounts, id), [
    { value: '', label: 'Do not switch Steam account' },
    { value: id, label: 'Friendly <name> (fixture-login)' },
  ]);
  assert.equal(steamAccountOptions([], id)[1].value, id);
  assert.match(steamAccountOptions([], id)[1].label, /not in account list/);
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

test('unknown names differ from confirmed missing accounts and known names are retained', () => {
  assert.equal(steamAccountOptions([], id, false)[1].label, 'Saved account (name unavailable)');
  assert.equal(steamAccountOptions([], id, true)[1].label, 'Saved account (not in account list)');
  assert.equal(steamAccountOptions([], id, true, [row])[1].label, 'Friendly <name> (fixture-login) (not in account list)');
  assert.equal(steamAccountOptions([], '', false).length, 1);
});

test('persisted policy accepts only Steam boolean forms and absent legacy key', () => {
  for (const value of [true, 'true', 'TRUE', '1', 'yes', 'On']) assert.equal(parseSavedSteamManagement({status:true,steam_account_management:value}), true);
  for (const value of [false, 'false', 'FALSE', '0', 'no', 'Off']) assert.equal(parseSavedSteamManagement({status:true,steam_account_management:value}), false);
  assert.equal(parseSavedSteamManagement({status:true}), undefined);
  for (const value of [null, 0, 1, '', 'maybe', 'false1', 'enabled', {}, []]) assert.throws(() => parseSavedSteamManagement({status:true,steam_account_management:value}));
  for (const payload of [null, {}, {status:false}, {status:'true'}]) assert.throws(() => parseSavedSteamManagement(payload));
});
