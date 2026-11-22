<script setup lang="ts">
// Ett protokoll med publicerade rättelser av fel i själva protokollet (#74) märks "Innehåller felaktigheter".
// Markeringen beskriver vad som står i protokollet, inte vem som gjort fel, och länkar till listan över
// felaktigheterna på sidan Avvikelser i protokollen.
import { computed } from 'vue'

const props = defineProps<{ sammantrade: { id: number; organ: { id: string }; datum: string | null; felaktigheter: number } }>()

const till = computed(() => {
  const ar = props.sammantrade.datum?.slice(0, 4)
  return {
    path: '/politik/avvikelser',
    query: { organ: props.sammantrade.organ.id, ...(ar ? { fran: ar, till: ar } : {}), felet: 'protokollet' },
    hash: `#protokoll-${props.sammantrade.id}`,
  }
})
</script>

<template>
  <RouterLink
    v-if="sammantrade.felaktigheter"
    :to="till"
    class="felaktigheter"
    data-testid="felaktigheter"
    :title="`${sammantrade.felaktigheter} ${sammantrade.felaktigheter === 1 ? 'uppgift' : 'uppgifter'} i protokollet har rättats av redaktionen`"
  >
    <span aria-hidden="true">!</span> Innehåller felaktigheter
  </RouterLink>
</template>

<style scoped>
.felaktigheter {
  display: inline-flex;
  gap: 4px;
  align-items: baseline;
  font-size: 12px;
  color: var(--ink-secondary);
  border: 1px solid var(--line-strong);
  border-radius: var(--radius);
  padding: 0 6px;
  text-decoration: none;
  white-space: nowrap;
}
.felaktigheter:hover {
  color: var(--accent);
  border-color: var(--accent);
}
.felaktigheter span {
  color: var(--status-warning);
  font-weight: 700;
}
</style>
