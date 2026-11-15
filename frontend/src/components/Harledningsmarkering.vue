<script setup lang="ts">
// Markering för ett parti som närvarolistan inte anger och som har härletts ur samma eller ett
// annat protokoll (docs/design.md, Säkerhetsmarkeringar). Läsaren kan fälla ut källan.
import type { PartiHarlett } from '../api'

defineProps<{ kalla: PartiHarlett }>()
</script>

<template>
  <details class="harlett" data-testid="parti-harlett" :data-grund="kalla.grund">
    <summary>
      <span class="ikon" aria-hidden="true">≈</span>
      Härlett
    </summary>
    <p class="detaljer">
      Närvarolistan anger inget parti.
      <template v-if="kalla.grund === 'samma_protokoll'">
        Partiet står vid personens namn på ett annat ställe i samma protokoll, till exempel i voteringslistan.
      </template>
      <template v-else-if="kalla.sammantrade">
        Partiet är det som närvarolistan anger vid
        <RouterLink :to="`/politik/sammantraden/${kalla.sammantrade.id}`"
          >{{ kalla.sammantrade.organ.namn }} {{ kalla.sammantrade.datum }}</RouterLink
        >, det närmaste sammanträdet med en partiuppgift.
      </template>
    </p>
  </details>
</template>

<style scoped>
.harlett {
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
  border: 1px dotted var(--line-strong);
  border-radius: var(--radius);
  padding: 0 6px;
}
summary::-webkit-details-marker {
  display: none;
}
.ikon {
  color: var(--ink-muted);
}
.detaljer {
  margin: 6px 0 0;
  padding: 8px 12px;
  border-left: 2px solid var(--line);
  max-width: 50ch;
  white-space: normal;
}
.detaljer a {
  color: var(--accent);
}
</style>
