<script setup lang="ts">
// Säkerhetsmarkering för automatiskt tolkade uppgifter (docs/design.md): plattformen har läst ut
// uppgiften ur protokollet, men ingen redaktör har granskat den. Ett protokoll som bara innehåller
// bilder läses med OCR (#52), och då kan även texten innehålla läsfel. Har redaktionen granskat
// protokollet (#176) visas datumet för granskningen, men inte vem som granskade. I listor räcker `kort`.
defineProps<{ ejTolkad?: boolean; ocr?: boolean; granskad?: string | null; kort?: boolean }>()
</script>

<template>
  <span v-if="ejTolkad" class="markering ej" data-testid="ej-tolkad" role="note">
    <span class="ikon" aria-hidden="true">!</span>
    Kunde inte tolkas automatiskt. Läs protokollet.
  </span>
  <span
    v-else-if="granskad"
    class="markering granskad"
    data-testid="granskat-protokoll"
    role="note"
    :title="`Redaktionen har jämfört tolkningen med protokollet ${granskad} och inte hittat några fel.${ocr ? ' Protokollet är publicerat som bilder och texten är läst med OCR (textigenkänning).' : ''}`"
  >
    <span class="ikon" aria-hidden="true">✓</span>
    <template v-if="kort">Granskad</template>
    <template v-else>Granskad av redaktionen {{ granskad }}<template v-if="ocr"> · läst med OCR</template></template>
  </span>
  <span
    v-else-if="ocr"
    class="markering"
    data-testid="last-med-ocr"
    role="note"
    title="Protokollet är publicerat som bilder utan text. Texten är läst med OCR (textigenkänning) och kan innehålla läsfel. Kontrollera mot protokollet."
  >
    <span class="ikon" aria-hidden="true">⚙</span>
    Läst med OCR, ej granskad
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
/* Granskad av en människa: hel kantlinje i stället för prickad. */
.granskad {
  border-style: solid;
  color: var(--ink);
}
.granskad .ikon {
  color: var(--ink-secondary);
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
