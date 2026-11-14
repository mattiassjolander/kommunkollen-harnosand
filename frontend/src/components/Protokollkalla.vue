<script setup lang="ts">
// Källrad för en uppgift ur ett protokoll: originalet hos kommunen och plattformens kopia.
import type { Protokollkalla } from '../api'
import { datum } from '../format'

defineProps<{ protokoll: Protokollkalla; paragraf?: number }>()
</script>

<template>
  <p class="kallrad" data-testid="kallrad">
    Källa:
    <a :href="protokoll.url" target="_blank" rel="noopener" data-testid="original">{{ protokoll.filnamn }}</a>
    <template v-if="paragraf"> § {{ paragraf }}</template>
    (harnosand.se) ·
    <a :href="protokoll.kopia" target="_blank" rel="noopener" data-testid="kopia">Sparad kopia</a>
    <template v-if="protokoll.version > 1"> · Version {{ protokoll.version }}</template>
    · Hämtad {{ datum(protokoll.hamtad) }}
    <span class="hash" :title="`SHA-256 ${protokoll.sha256}`">· SHA-256 {{ protokoll.sha256.slice(0, 12) }}…</span>
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
.hash {
  font-variant-numeric: tabular-nums;
}
</style>
