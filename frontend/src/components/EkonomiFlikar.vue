<script setup lang="ts">
// Undernavigering i Ekonomi.
</script>

<template>
  <nav class="flikar" aria-label="Ekonomi">
    <RouterLink to="/ekonomi" exact-active-class="aktiv">Nyckeltal</RouterLink>
    <RouterLink to="/ekonomi/skatteunderlag" exact-active-class="aktiv">Skatteunderlagsprognos</RouterLink>
    <RouterLink to="/ekonomi/budget-och-utfall" exact-active-class="aktiv">Budget och utfall</RouterLink>
  </nav>
</template>

<style scoped>
.flikar {
  display: flex;
  flex-wrap: wrap;
  column-gap: 20px;
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
