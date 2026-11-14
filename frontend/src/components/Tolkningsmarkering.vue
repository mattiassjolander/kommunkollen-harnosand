<script setup lang="ts">
// Säkerhetsmarkering för automatiskt tolkade uppgifter (docs/design.md): plattformen har läst ut
// uppgiften ur protokollet, men ingen redaktör har granskat den.
defineProps<{ ejTolkad?: boolean }>()
</script>

<template>
  <span v-if="ejTolkad" class="markering ej" data-testid="ej-tolkad" role="note">
    <span class="ikon" aria-hidden="true">!</span>
    Kunde inte tolkas automatiskt. Läs protokollet.
  </span>
  <span
    v-else
    class="markering"
    data-testid="automatiskt-tolkad"
    role="note"
    title="Uppgiften är automatiskt läst ur protokollet och inte granskad av redaktionen. Kontrollera mot protokollet."
  >
    <span class="ikon" aria-hidden="true">⚙</span>
    Automatiskt tolkad, ej granskad
  </span>
</template>

<style scoped>
.markering {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  font-size: 12px;
  color: var(--ink-secondary);
  border: 1px dotted var(--line-strong);
  border-radius: var(--radius);
  padding: 2px 8px;
  white-space: nowrap;
}
.ikon {
  font-size: 11px;
  color: var(--ink-muted);
}
.ej .ikon {
  display: inline-grid;
  place-items: center;
  width: 14px;
  height: 14px;
  border-radius: 50%;
  background: var(--status-warning);
  color: #0b0b0b;
  font-weight: 600;
}
</style>
