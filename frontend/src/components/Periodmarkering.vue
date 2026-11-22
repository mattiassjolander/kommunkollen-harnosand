<script setup lang="ts">
// Markering för ett parti som redaktionen har fastställt för en period (#100, ADR-0006, docs/design.md,
// Säkerhetsmarkeringar). Visas bara när perioden ändrade partiet som protokollet anger. Läsaren kan fälla ut
// vad protokollet anger, perioden och motiveringen.
import type { Periodmarkering } from '../api'
import { parti as partitext } from '../format'

defineProps<{ period: Periodmarkering }>()
</script>

<template>
  <details class="period" data-testid="partitillhorighet" :data-protokollet="period.protokollet ?? ''">
    <summary>
      <span class="ikon" aria-hidden="true">◆</span>
      Fastställt av redaktionen
    </summary>
    <p class="detaljer">
      Parti fastställt av redaktionen för perioden {{ period.fran }} –
      {{ period.till ?? 'tills vidare' }}.
      <template v-if="period.protokollet === null">Protokollet anger inget parti.</template>
      <template v-else>Protokollet anger {{ partitext(period.protokollet) }}.</template>
      <span class="motivering">{{ period.motivering }}</span>
    </p>
  </details>
</template>

<style scoped>
.period {
  display: inline-block;
  font-size: 12px;
  color: var(--ink-secondary);
  vertical-align: baseline;
}
summary {
  cursor: pointer;
  display: inline-flex;
  align-items: center;
  gap: 6px;
  list-style: none;
  border: 1px solid var(--line-strong);
  border-radius: var(--radius);
  padding: 0 6px;
}
summary::-webkit-details-marker {
  display: none;
}
.ikon {
  color: var(--ink-muted);
  font-size: 10px;
}
.detaljer {
  margin: 6px 0 0;
  padding: 8px 12px;
  border-left: 2px solid var(--line);
  max-width: 50ch;
  white-space: normal;
}
.motivering {
  display: block;
  margin-top: 4px;
  font-style: italic;
}
</style>
