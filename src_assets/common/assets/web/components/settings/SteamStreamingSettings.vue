<script setup lang="ts">
import { onBeforeUnmount, ref, watch } from 'vue';
import { apiGet, apiPatch, apiPost } from '@/api/client';
import { AppButton } from '@/components/ui';
import { parseRememberedSteamAccounts, steamAccountOptions, type RememberedSteamAccount } from '@/utils/steamAccounts';
export interface StreamingStatus {
  supported: boolean; available: boolean; account_management: boolean;
  migration_pending: boolean; resolution_automation: boolean;
}
interface ClientAssignment { uuid: string; name: string; assignment: string; saved: string; notice: string; error: string }
const props = defineProps<{ status: StreamingStatus; refreshing?: boolean; statusError?: boolean; savedAccountManagement?: boolean }>();
const emit = defineEmits<{ changed: [] }>();
const busy = ref(false), loading = ref(false);
const savingPolicy = ref(false), savedManagement = ref(false);
const policyError = ref(''), policyNotice = ref(''), accountError = ref(''), clientError = ref('');
const management = ref(props.status.account_management);
const pendingManagement = ref<boolean | null>(null);
const pendingTiming = ref<'session' | 'restart' | null>(null);
let refreshQueued = false;
const accounts = ref<RememberedSteamAccount[]>([]), knownAccounts = ref<RememberedSteamAccount[]>([]);
const loaded = ref(false), clients = ref<ClientAssignment[]>([]);
let generation = 0;
onBeforeUnmount(() => ++generation);
watch([() => props.status.account_management, () => props.savedAccountManagement, () => props.refreshing, () => props.statusError, busy], () => {
  if (busy.value || props.refreshing) return;
  if (props.statusError) {
    if (savedManagement.value) {
      savedManagement.value = false; policyNotice.value = '';
      policyError.value = 'The setting was saved, but current status could not be refreshed.';
    }
    return;
  }
  if (policyError.value === 'The setting was saved, but current status could not be refreshed.') policyError.value = '';
  const desired = props.savedAccountManagement ?? props.status.account_management;
  if (pendingManagement.value !== null && desired === props.status.account_management) { policyNotice.value = 'Saved.'; savedManagement.value = true; }
  management.value = desired;
  if (pendingManagement.value !== desired || desired === props.status.account_management) pendingTiming.value = null;
  pendingManagement.value = desired === props.status.account_management ? null : desired;
}, { immediate: true });
function options(client: ClientAssignment) {
  return steamAccountOptions(accounts.value, client.assignment, loaded.value, knownAccounts.value);
}
async function refresh() {
  if (busy.value) { refreshQueued = true; return; }
  const request = ++generation;
  if (!props.status.supported || !props.status.account_management) { loading.value = false; return; }
  loading.value = true; accountError.value = ''; clientError.value = '';
  // Separate failures: account lookup cannot erase device assignments or cached names.
  await Promise.all([
    (async () => {
      try {
        const data = await apiGet<{ status?: boolean; named_certs?: { uuid: string; name: string; steam_account_id?: string }[] }>('/api/clients/list');
        if (request !== generation) return;
        if (data.status === false || !Array.isArray(data.named_certs)) throw new Error();
        clients.value = data.named_certs.map(c => {
          const previous = clients.value.find(p => p.uuid === c.uuid);
          const saved = c.steam_account_id ?? '';
          const dirty = previous && previous.assignment !== previous.saved;
          return { uuid: c.uuid, name: c.name || 'Unknown device', saved,
            assignment: dirty ? previous.assignment : saved,
            notice: previous && previous.saved !== saved ? (dirty ? 'Saved assignment changed. Your unsaved selection is retained.' : '') : previous?.notice ?? '',
            error: previous?.error ?? '' };
        });
      } catch { if (request === generation) clientError.value = 'Device assignments could not be loaded.'; }
    })(),
    (async () => {
      try {
        if (!props.status.available) throw new Error();
        const result = parseRememberedSteamAccounts(await apiGet('/api/clients/steam-accounts', { cache: 'no-store' }));
        if (request !== generation) return;
        accounts.value = result;
        knownAccounts.value = [...new Map([...knownAccounts.value, ...result].map(a => [a.steam_id, a])).values()];
        loaded.value = true;
      } catch { if (request === generation) accountError.value = props.status.available ? 'Steam accounts could not be loaded.' : 'Steam or the companion runtime is unavailable.'; }
    })(),
  ]);
  if (request !== generation) return;
  loading.value = false;
}
watch([() => props.status.supported, () => props.status.account_management, () => props.status.available], refresh, { immediate: true });
async function setPolicy(key: 'steam_account_management' | 'steam_resolution_automation', event: Event) {
  const checkbox = event.target as HTMLInputElement;
  const enabled = checkbox.checked;
  if (busy.value || props.refreshing || props.statusError) { checkbox.checked = key === 'steam_account_management' ? management.value : props.status.resolution_automation; return; }
  const previous = key === 'steam_account_management' ? management.value : props.status.resolution_automation;
  busy.value = true; savingPolicy.value = true; savedManagement.value = false; policyError.value = ''; policyNotice.value = '';
  try {
    const result = await apiPatch<{ status?: boolean; deferred?: boolean; restartRequired?: boolean }>('/api/config', { [key]: enabled });
    if (result.status !== true) throw new Error();
    if (key === 'steam_account_management') {
      ++generation; loading.value = false; management.value = enabled; savedManagement.value = true;
      pendingManagement.value = result.deferred || result.restartRequired ? enabled : null;
      pendingTiming.value = result.deferred ? 'session' : result.restartRequired ? 'restart' : null;
    }
    policyNotice.value = result.deferred || result.restartRequired ? 'Saved. Changes take effect after the active session ends or the required host restart.' : 'Saved.';
    emit('changed');
  } catch {
    checkbox.checked = previous;
    policyError.value = key === 'steam_account_management'
      ? pendingManagement.value !== null ? 'Could not save. The previous saved choice is unchanged.' : `Could not save. Account management is still ${previous ? 'enabled' : 'disabled'}.`
      : 'The setting could not be saved.';
  } finally { busy.value = false; savingPolicy.value = false; if (refreshQueued) { refreshQueued = false; void refresh(); } }
}
async function save(client: ClientAssignment) {
  const assignment = client.assignment;
  busy.value = true; client.error = ''; client.notice = '';
  ++generation; loading.value = false;
  try {
    const result = await apiPost<{ status?: boolean }>('/api/clients/update', { uuid: client.uuid, steam_account_id: assignment });
    if (result.status !== true) throw new Error();
    const current = clients.value.find(row => row.uuid === client.uuid);
    if (current) { current.saved = assignment; current.notice = 'Assignment saved.'; }
  } catch {
    const current = clients.value.find(row => row.uuid === client.uuid);
    if (current) current.error = 'The assignment could not be saved. Your selection has not been saved.';
  } finally { busy.value = false; if (refreshQueued) { refreshQueued = false; void refresh(); } }
}
</script>
<template>
  <section class="steam-streaming" id="steam-streaming" aria-label="Steam streaming automation">
    <h3>Steam streaming automation</h3>
    <p v-if="!status.supported">Account and resolution automation are not supported on this platform. Saved assignments are retained.</p>
    <template v-else>
      <p>These options are independent of Steam library discovery. Desktop and other launchers remain available.</p>
      <label><input type="checkbox" :checked="management" :disabled="busy || refreshing || statusError" @change="setPolicy('steam_account_management', $event)" /> Manage Steam accounts for streaming</label>
      <p role="status">{{ savingPolicy ? 'Saving…' : statusError ? 'Current status unavailable' : pendingManagement !== null ? `Currently ${status.account_management ? 'enabled' : 'disabled'} · ${pendingManagement ? 'Enable' : 'Disable'} pending` : management ? 'Enabled' : 'Disabled' }}<template v-if="savedManagement && policyNotice === 'Saved.' && !policyError"> · Saved</template></p>
      <p v-if="pendingManagement !== null && !policyError && !statusError" role="status">{{ pendingTiming === 'session' ? 'Saved choice applies after the active session ends.' : pendingTiming === 'restart' ? 'Saved choice requires a host restart.' : 'Saved choice is not active yet.' }}</p>
      <p v-if="pendingManagement === null && policyNotice && (policyNotice !== 'Saved.' || !savedManagement)" role="status">{{ policyNotice }}</p>
      <p v-if="statusError && !policyError" role="alert">The saved Steam account policy could not be refreshed. Retry Refresh status.</p>
      <p v-if="policyError" role="alert">{{ policyError }}</p>
      <label><input type="checkbox" :checked="status.resolution_automation" :disabled="busy || refreshing || statusError" @change="setPolicy('steam_resolution_automation', $event)" /> Adjust supported games to stream resolution</label>
      <p>Resolution changes require supported game configuration and safe Steam/game state. Unsupported games remain unchanged.</p>
      <p v-if="!status.available" role="status">Steam or the companion runtime is unavailable. Assignments are retained. Protected Steam launches wait for verification; Desktop and other launchers remain available.</p>
      <div v-if="management">
        <div class="steam-streaming__header">
          <h4>Steam account assignments</h4>
          <AppButton type="button" size="compact" :disabled="busy || loading" @click="refresh">{{ loading ? 'Loading…' : accountError || clientError ? 'Retry' : 'Reload accounts' }}</AppButton>
        </div>
        <p>“Do not switch Steam account” uses the account already signed in when this device starts streaming.</p>
        <p v-if="loading" role="status">Loading Steam accounts…</p>
        <p v-else-if="accountError" role="alert">{{ accountError }}</p>
        <p v-else-if="loaded && !accounts.length" role="status">No remembered Steam accounts found.</p>
        <p v-if="clientError" role="alert">{{ clientError }}</p>
        <div class="steam-streaming__assignment" v-for="client in clients" :key="client.uuid">
          <label :for="`steam-assignment-${client.uuid}`">{{ client.name }}</label>
          <select class="vs-input" :id="`steam-assignment-${client.uuid}`" v-model="client.assignment" :disabled="busy || loading || !!accountError || !!clientError" @change="client.notice = ''; client.error = ''">
            <option v-for="option in options(client)" :key="option.value" :value="option.value">{{ option.label }}</option>
          </select>
          <AppButton type="button" size="compact" :disabled="busy || loading || !!accountError || !!clientError || client.assignment === client.saved" @click="save(client)">Save assignment</AppButton>
          <p v-if="client.notice" class="steam-streaming__feedback" role="status">{{ client.notice }}</p>
          <p v-if="client.error" class="steam-streaming__feedback" role="alert">{{ client.error }}</p>
        </div>
      </div>
    </template>
  </section>
</template>
<style scoped>
.steam-streaming { display: grid; gap: 0.75rem; margin-top: 1rem; }
.steam-streaming h3, .steam-streaming h4, .steam-streaming p { margin: 0; }
.steam-streaming > label { display: flex; align-items: center; gap: 0.5rem; }
.steam-streaming__header { display: flex; align-items: center; justify-content: space-between; gap: 0.75rem; margin-bottom: 0.75rem; }
.steam-streaming__assignment { display: grid; grid-template-columns: minmax(7rem, 1fr) minmax(12rem, 2fr) auto; align-items: center; gap: 0.75rem; margin-top: 0.75rem; }
.steam-streaming__feedback { grid-column: 2 / -1; }
@media (max-width: 640px) { .steam-streaming__assignment { grid-template-columns: 1fr; } .steam-streaming__feedback { grid-column: 1; } }
</style>
