<script setup lang="ts">
import { ref, watch } from 'vue';
import { apiGet, apiPatch, apiPost } from '@/api/client';
import { parseRememberedSteamAccounts, steamAccountOptions, type RememberedSteamAccount } from '@/utils/steamAccounts';
export interface StreamingStatus {
  supported: boolean; available: boolean; account_management: boolean;
  migration_pending: boolean; resolution_automation: boolean;
}
const props = defineProps<{ status: StreamingStatus }>();
const emit = defineEmits<{ changed: [] }>();
const busy = ref(false), error = ref(''), notice = ref('');
const accounts = ref<RememberedSteamAccount[]>([]);
const clients = ref<{ uuid: string; name: string; assignment: string }[]>([]);
async function refresh() {
  if (!props.status.supported || !props.status.account_management) return;
  error.value = '';
  try {
    const data = await apiGet<{ status?: boolean; named_certs?: { uuid: string; name: string; steam_account_id?: string }[] }>('/api/clients/list');
    if (data.status === false) throw new Error();
    clients.value = (data.named_certs ?? []).map(c => ({ uuid: c.uuid, name: c.name, assignment: c.steam_account_id ?? '' }));
    accounts.value = [];
    if (props.status.available)
      accounts.value = parseRememberedSteamAccounts(await apiGet('/api/clients/steam-accounts', { cache: 'no-store' }));
  } catch { error.value = 'Accounts could not be refreshed. Saved assignments are unchanged.'; }
}
watch(() => [props.status.account_management, props.status.available], refresh, { immediate: true });
async function setPolicy(key: 'steam_account_management' | 'steam_resolution_automation', enabled: boolean) {
  busy.value = true; error.value = '';
  try {
    const result = await apiPatch<{ status?: boolean; deferred?: boolean; restartRequired?: boolean }>('/api/config', { [key]: enabled });
    if (result.status === false) throw new Error();
    notice.value = result.deferred || result.restartRequired ? 'Saved. Changes take effect after the active session ends or the required host restart.' : 'Saved.';
    emit('changed');
  } catch { error.value = 'The setting could not be saved.'; }
  finally { busy.value = false; }
}
async function save(client: { uuid: string; assignment: string }) {
  busy.value = true; error.value = '';
  try {
    const result = await apiPost<{ status?: boolean }>('/api/clients/update', { uuid: client.uuid, steam_account_id: client.assignment });
    if (result.status !== true) throw new Error();
    await refresh();
  } catch { error.value = 'The assignment could not be saved. Refresh before retrying.'; }
  finally { busy.value = false; }
}
</script>
<template>
  <section class="steam-streaming" id="steam-streaming" aria-label="Steam streaming automation">
    <h3>Steam streaming automation</h3>
    <p v-if="!status.supported">Account and resolution automation are not supported on this platform. Saved assignments are retained.</p>
    <template v-else>
      <p>These options are independent of Steam library discovery. Desktop and other launchers remain available.</p>
      <p v-if="status.migration_pending" role="status">Existing assignments were retained with Steam launch protection enabled. Review them, then explicitly keep or disable account management.</p>
      <label><input type="checkbox" :checked="status.account_management" :disabled="busy" @change="setPolicy('steam_account_management', ($event.target as HTMLInputElement).checked)" /> Manage Steam accounts for streaming</label>
      <button v-if="status.migration_pending" type="button" :disabled="busy" @click="setPolicy('steam_account_management', true)">Keep account management enabled</button>
      <label><input type="checkbox" :checked="status.resolution_automation" :disabled="busy" @change="setPolicy('steam_resolution_automation', ($event.target as HTMLInputElement).checked)" /> Adjust supported games to stream resolution</label>
      <p>Resolution changes require supported game configuration and safe Steam/game state. Unsupported games remain unchanged.</p>
      <p v-if="!status.available" role="status">Steam or the companion runtime is unavailable. Assignments are retained. Protected Steam launches wait for verification; Desktop and other launchers remain available.</p>
      <div v-if="status.account_management">
        <button type="button" :disabled="busy" @click="refresh">Refresh assignments</button>
        <div class="steam-streaming__assignment" v-for="client in clients" :key="client.uuid">
          <label :for="`steam-assignment-${client.uuid}`">{{ client.name }}</label>
          <select class="vs-input" :id="`steam-assignment-${client.uuid}`" v-model="client.assignment" :disabled="busy">
            <option v-for="option in steamAccountOptions(accounts, client.assignment)" :key="option.value" :value="option.value">{{ option.label }}</option>
          </select>
          <button type="button" :disabled="busy" @click="save(client)">Save assignment</button>
        </div>
      </div>
    </template>
    <p v-if="notice" role="status">{{ notice }}</p>
    <p v-if="error" role="alert">{{ error }}</p>
  </section>
</template>

<style scoped>
.steam-streaming { display: grid; gap: 0.75rem; margin-top: 1rem; }
.steam-streaming h3, .steam-streaming p { margin: 0; }
.steam-streaming > label { display: flex; align-items: center; gap: 0.5rem; }
.steam-streaming__assignment { display: grid; grid-template-columns: minmax(7rem, 1fr) minmax(12rem, 2fr) auto; align-items: center; gap: 0.75rem; margin-top: 0.75rem; }
@media (max-width: 640px) { .steam-streaming__assignment { grid-template-columns: 1fr; } }
</style>
