<script setup lang="ts">
// Behandlingarna som räknats bakom en rad i en topplista (#163), utfällbara så att siffran går att kontrollera.
import type { Topplistebehandling } from '../api'
import { sammantradesdatum, tal } from '../format'

defineProps<{ behandlingar: Topplistebehandling[] }>()
</script>

<template>
  <details v-if="behandlingar.length" class="raknade" data-testid="raknade">
    <summary>{{ tal(behandlingar.length) }} {{ behandlingar.length === 1 ? 'behandling' : 'behandlingar' }}</summary>
    <ul>
      <li v-for="b in behandlingar" :key="`${b.sammantrade.id}-${b.paragraf}`">
        <RouterLink :to="`/politik/sammantraden/${b.sammantrade.id}/paragraf/${b.paragraf}`" data-testid="raknad">{{
          b.rubrik
        }}</RouterLink>
        <span class="meta">{{ b.sammantrade.organ.namn }} {{ sammantradesdatum(b.sammantrade.datum) }} § {{ b.paragraf }}</span>
      </li>
    </ul>
  </details>
  <span v-else class="inga">–</span>
</template>

<style scoped>
.raknade summary {
  cursor: pointer;
  color: var(--accent);
  font-size: 13px;
  white-space: nowrap;
}
.raknade ul {
  list-style: none;
  margin: 8px 0 0;
  padding: 0;
  display: grid;
  gap: 6px;
  min-width: 16rem;
}
.raknade li {
  display: grid;
  gap: 2px;
  font-size: 13px;
}
.meta {
  font-size: 12px;
  color: var(--ink-secondary);
}
.inga {
  color: var(--ink-muted);
}
</style>
