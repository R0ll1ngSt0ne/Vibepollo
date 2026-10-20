export interface RememberedSteamAccount {
  steam_id: string;
  account_name: string;
  persona_name: string;
}

export function parseRememberedSteamAccounts(payload: unknown): RememberedSteamAccount[] {
  const data = payload as { status?: unknown; accounts?: unknown } | null;
  if (data?.status !== 'available' || !Array.isArray(data.accounts) || data.accounts.length > 64)
    throw new Error('account-list-unavailable');
  const seen = new Set<string>();
  return data.accounts.map((row: unknown) => {
    const item = row as Partial<RememberedSteamAccount> | null;
    const id = item?.steam_id;
    if (typeof id !== 'string' || !/^[0-9]{17}$/.test(id) ||
        id <= '76561197960265728' || id > '76561202255233023' || seen.has(id) ||
        typeof item?.account_name !== 'string' || !item.account_name.trim() || item.account_name.length > 64 ||
        typeof item.persona_name !== 'string' || item.persona_name.length > 128 ||
        /[\x00-\x1f\x7f]/.test(item.account_name + item.persona_name))
      throw new Error('invalid-account-list');
    seen.add(id);
    return { steam_id: id, account_name: item.account_name, persona_name: item.persona_name };
  });
}

export function steamAccountOptions(accounts: RememberedSteamAccount[], assigned: string) {
  const options = [{ value: '', label: 'Keep current account' }];
  for (const account of accounts) options.push({
    value: account.steam_id,
    label: account.persona_name.trim()
      ? `${account.persona_name} (${account.account_name})`
      : account.account_name,
  });
  if (assigned && !accounts.some((account) => account.steam_id === assigned))
    options.push({ value: assigned, label: 'Previously assigned account (not currently listed)' });
  return options;
}
