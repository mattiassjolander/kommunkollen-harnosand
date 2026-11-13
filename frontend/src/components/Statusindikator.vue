<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { hamtaStatus, type GlobalStatus } from '../api'
import { datumTid } from '../format'
import StatusMarkering from './StatusMarkering.vue'

const status = ref<GlobalStatus | null>(null)
const fel = ref(false)

onMounted(async () => {
  try {
    status.value = await hamtaStatus()
  } catch {
    fel.value = true
  }
})
</script>

<template>
  <div class="indikator" data-testid="statusindikator" aria-label="Datainsamlingens status">
    <template v-if="status">
      <template v-if="status.senaste_korning">
        <StatusMarkering
          :status="status.fullstandigt_uppdaterad ? 'lyckad' : 'delvis_fel'"
          :text="status.fullstandigt_uppdaterad ? 'Fullständigt uppdaterad' : 'Delvis inaktuell'"
        />
        <span><span class="etikett">Senaste insamling:</span> {{ datumTid(status.senaste_korning.avslutad) }}</span>
        <span>
          <span class="etikett">Senast lyckad:</span>
          {{ status.senaste_lyckade_korning ? datumTid(status.senaste_lyckade_korning.avslutad) : 'ingen än' }}
        </span>
        <span v-if="status.nasta_korning" data-testid="nasta-korning">
          <span class="etikett">Nästa insamling:</span> {{ datumTid(status.nasta_korning) }}
        </span>
        <span>
          <span class="etikett">Datakällor:</span>
          {{ status.kallor_utan_fel }} av {{ status.kallor_kontrollerade }} kontrollerade utan fel
        </span>
      </template>
      <StatusMarkering v-else status="aldrig" text="Ingen insamling har körts än" />
      <span v-if="!status.senaste_korning && status.nasta_korning" data-testid="nasta-korning">
        <span class="etikett">Nästa insamling:</span> {{ datumTid(status.nasta_korning) }}
      </span>
      <RouterLink to="/datakallor" class="lank">Visa datakällor</RouterLink>
    </template>
    <span v-else-if="fel" class="etikett">Uppdateringsstatus kunde inte hämtas.</span>
  </div>
</template>

<style scoped>
.indikator {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 4px 24px;
  font-size: 12px;
  color: var(--ink);
  min-height: 20px;
}
.etikett {
  color: var(--ink-muted);
}
.lank {
  margin-left: auto;
}
</style>
