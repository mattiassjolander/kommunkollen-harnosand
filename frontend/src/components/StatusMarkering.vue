<script setup lang="ts">
import { computed } from 'vue'

// Status visas alltid med färg, ikon och text (docs/design.md). Färgen sitter bara på ikonen,
// texten har vanlig textfärg så att den går att läsa även för gult.
type Status = 'lyckad' | 'inga_nya' | 'delvis_fel' | 'misslyckad' | 'pagar' | 'avbruten' | 'aldrig'

const props = defineProps<{ status: Status | null; text?: string }>()

const VISNING: Record<Status, { ikon: string; text: string }> = {
  lyckad: { ikon: '✓', text: 'Lyckad' },
  inga_nya: { ikon: '–', text: 'Inga nya uppgifter' },
  delvis_fel: { ikon: '!', text: 'Delvis fel' },
  misslyckad: { ikon: '✕', text: 'Misslyckad' },
  pagar: { ikon: '…', text: 'Pågår' },
  avbruten: { ikon: '!', text: 'Avbruten' },
  aldrig: { ikon: '–', text: 'Aldrig kontrollerad' },
}

const s = computed<Status>(() => props.status ?? 'aldrig')
</script>

<template>
  <span class="status" :data-status="s" data-testid="status">
    <span class="ikon" :class="s" aria-hidden="true">{{ VISNING[s].ikon }}</span>
    <span>{{ text ?? VISNING[s].text }}</span>
  </span>
</template>

<style scoped>
.status {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  white-space: nowrap;
}
.ikon {
  display: inline-grid;
  place-items: center;
  width: 16px;
  height: 16px;
  border-radius: 50%;
  font-size: 11px;
  font-weight: 600;
  line-height: 1;
  color: #ffffff;
}
.lyckad {
  background: var(--status-good);
}
.delvis_fel,
.avbruten {
  background: var(--status-warning);
  color: #0b0b0b;
}
.misslyckad {
  background: var(--status-critical);
}
.inga_nya,
.pagar,
.aldrig {
  background: none;
  border: 1px solid var(--ink-muted);
  color: var(--ink-muted);
}
</style>
