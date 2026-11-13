<script setup lang="ts">
import { computed } from 'vue'
import type { Serie } from '../api'
import { datum } from '../format'

const props = defineProps<{ serie: Serie; perioder: string[] }>()

const kpiId = computed(() => props.serie.matt.id.split(':').pop())
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
    <a :href="serie.matt.datakalla.url" target="_blank" rel="noopener">{{ serie.matt.datakalla.titel }}</a>
    ({{ kpiId }}) · Avser {{ avser }} · Publicerad {{ datum(serie.matt.kallans_publicering) }} · Hämtad
    {{ datum(senastHamtad) }}
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
