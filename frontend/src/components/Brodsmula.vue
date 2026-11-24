<script setup lang="ts">
// Brödsmulan ovanför vyns rubrik (#146): huvudvyn, och för en detaljsida också undervyn.
// Visas bara i huvudvyer med undervyer.
import { computed } from 'vue'
import { useRoute } from 'vue-router'
import { plats } from '../navigering'

const route = useRoute()
const leder = computed(() => {
  const p = plats(route.path)
  if (!p?.huvudvy.undervyer) return []
  const huvud = { namn: p.huvudvy.namn, till: p.huvudvy.undervyer[0].till }
  return p.undervy && !p.exakt && p.undervy.till !== huvud.till ? [huvud, p.undervy] : [huvud]
})
</script>

<template>
  <nav v-if="leder.length" class="brodsmula" aria-label="Du är här" data-testid="brodsmula">
    <template v-for="l in leder" :key="l.till">
      <RouterLink :to="l.till">{{ l.namn }}</RouterLink>
      <span aria-hidden="true"> › </span>
    </template>
  </nav>
</template>

<style scoped>
.brodsmula {
  font-size: 13px;
  color: var(--ink-muted);
  margin-bottom: 4px;
}
.brodsmula a {
  color: var(--ink-secondary);
  text-decoration: none;
}
.brodsmula a:hover {
  color: var(--accent);
  text-decoration: underline;
}
</style>
