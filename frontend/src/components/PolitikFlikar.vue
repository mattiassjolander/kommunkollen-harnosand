<script setup lang="ts">
// Undernavigering i Politik och beslut. Kopplingsförslag och rättelser visas för redaktörer och utgivare.
import { computed, inject, ref, type Ref } from 'vue'
import type { Jag } from '../api'

const jag = inject<Ref<Jag | null>>('jag', ref(null))
const arRedaktor = computed(() => jag.value?.roller.includes('redaktor') ?? false)
const arUtgivare = computed(() => jag.value?.roller.includes('utgivare') ?? false)
</script>

<template>
  <nav class="flikar" aria-label="Politik och beslut">
    <RouterLink to="/politik" exact-active-class="aktiv">Sammanträden</RouterLink>
    <RouterLink to="/politik/ledamoter" exact-active-class="aktiv">Ledamöter</RouterLink>
    <RouterLink to="/politik/statistik" exact-active-class="aktiv">Statistik</RouterLink>
    <RouterLink to="/politik/avvikelser" exact-active-class="aktiv">Avvikelser</RouterLink>
    <RouterLink v-if="arRedaktor" to="/politik/kopplingar" exact-active-class="aktiv">Kopplingsförslag</RouterLink>
    <RouterLink v-if="arRedaktor || arUtgivare" to="/politik/rattelser" exact-active-class="aktiv">Rättelser</RouterLink>
  </nav>
</template>

<style scoped>
.flikar {
  display: flex;
  gap: 20px;
  border-bottom: 1px solid var(--line);
  margin-bottom: 24px;
  font-size: 14px;
}
.flikar a {
  padding: 6px 0;
  color: var(--ink-secondary);
  text-decoration: none;
  border-bottom: 2px solid transparent;
  margin-bottom: -1px;
}
.flikar a:hover {
  color: var(--ink);
}
.flikar a.aktiv {
  color: var(--ink);
  font-weight: 600;
  border-bottom-color: var(--accent);
}
</style>
