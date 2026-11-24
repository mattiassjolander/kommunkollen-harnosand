<script setup lang="ts">
import { computed } from 'vue'
import type { Serie } from '../api'
import { datum } from '../format'

const props = defineProps<{
  serie: Serie
  perioder: string[]
  prisniva?: string | null
  /** Vem som tar fram uppgifterna, när det inte är datakällan själv, t.ex. "SCB" för SCB/Kolada. */
  producent?: string
}>()

// "kolada:N03007" → "N03007", "scb:BalansKnN:065" → "BalansKnN, post 065". Beräknade mått har ingen beteckning.
const beteckning = computed(() => {
  const delar = props.serie.matt.id.split(':').slice(1)
  if (delar.length === 2) return `${delar[0]}, post ${delar[1]}`
  return /^[A-Z]\d+$/.test(delar[0] ?? '') ? delar[0] : null
})
const avser = computed(() =>
  props.perioder.length ? `${props.perioder[0]}–${props.perioder[props.perioder.length - 1]}` : '–',
)
const senastHamtad = computed(() => {
  const tider = props.serie.punkter.map((p) => p.hamtad).sort()
  return tider.length ? tider[tider.length - 1] : null
})
</script>

<template>
  <p class="kallrad" data-testid="kallrad">
    Källa:
    <template v-if="producent">{{ producent }}/</template><a :href="serie.matt.datakalla.url" target="_blank" rel="noopener">{{ serie.matt.datakalla.titel }}</a>
    {{ beteckning ? ` (${beteckning})` : "" }} · Avser {{ avser }}
    <template v-if="prisniva"> · {{ prisniva[0].toUpperCase() + prisniva.slice(1) }}</template> · Publicerad
    {{ datum(serie.matt.kallans_publicering) }} · Hämtad {{ datum(senastHamtad) }}
  </p>
</template>

<style scoped>
.kallrad {
  font-size: 12px;
  color: var(--ink-muted);
  margin: 12px 0 0;
}
.kallrad a {
  color: inherit;
}
</style>
