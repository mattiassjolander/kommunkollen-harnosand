<script setup lang="ts">
// Undernavigering i Politik och beslut.
</script>

<template>
  <nav class="flikar" aria-label="Politik och beslut">
    <RouterLink to="/politik" exact-active-class="aktiv">Sammanträden</RouterLink>
    <RouterLink to="/politik/ledamoter" exact-active-class="aktiv">Ledamöter</RouterLink>
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
