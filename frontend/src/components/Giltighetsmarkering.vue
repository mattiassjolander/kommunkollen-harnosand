<script setup lang="ts">
import { computed } from 'vue'
import type { Giltighet } from '../api'
import { datum } from '../format'

// Ett styrande dokuments giltighet (#63). Gällande står utan ram. Utgånget och borttaget står i en ram, med datumet.
// Texten är saklig och säger varifrån giltigheten kommer.

const props = defineProps<{ giltighet: Giltighet; utforlig?: boolean }>()

const etikett = computed(() => {
  const g = props.giltighet
  if (g.status === 'borttaget') return `Borttaget ${datum(g.borttagen ?? null)}`
  if (g.status === 'utganget') return `Utgånget ${datum(g.till)}`
  return g.till ? `Gällande t o m ${datum(g.till)}` : 'Gällande'
})
</script>

<template>
  <span class="giltighet" :class="giltighet.status" data-testid="giltighetsmarkering" :data-status="giltighet.status">
    <span class="etikett">{{ etikett }}</span>
    <span v-if="utforlig" class="text">{{ giltighet.text }}</span>
  </span>
</template>

<style scoped>
.giltighet {
  display: inline-flex;
  flex-wrap: wrap;
  align-items: baseline;
  gap: 8px;
}
.utganget .etikett,
.borttaget .etikett {
  border: 1px solid var(--line-strong);
  border-radius: var(--radius);
  padding: 0 6px;
  white-space: nowrap;
}
.text {
  color: var(--ink-secondary);
}
</style>
