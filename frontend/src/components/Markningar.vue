<script setup lang="ts">
// Märkningarna på en behandling eller ett ärende som små chips (docs/design.md, Märkningar, #162).
// Votering, Reservation och Oenighet har var sin dämpade, neutrala ton, resten är konturchips. Varje chip har
// text, så färgen bär aldrig betydelse ensam.
import { MARKNINGAR, type Markning } from '../api'

defineProps<{ markningar: Markning[] }>()

const FYLLDA = new Set(['votering', 'reservation', 'oenighet'])
const NAMN = new Map(MARKNINGAR.map((m) => [m.id, m.namn]))

function titel(m: Markning): string | undefined {
  if (m.antal && m.antal > 1) return `${NAMN.get(m.id) ?? m.text} vid ${m.antal} behandlingar`
  return undefined
}
</script>

<template>
  <ul v-if="markningar.length" class="markningar" aria-label="Märkningar" data-testid="markningar">
    <li
      v-for="m in markningar"
      :key="m.id"
      class="chip"
      :class="[FYLLDA.has(m.id) ? `fylld ${m.id}` : 'kontur']"
      :title="titel(m)"
      data-testid="markning"
      :data-markning="m.id"
    >
      {{ m.text }}
    </li>
  </ul>
</template>

<style scoped>
.markningar {
  display: inline-flex;
  flex-wrap: wrap;
  gap: 4px;
  list-style: none;
  margin: 0;
  padding: 0;
  vertical-align: baseline;
}
.chip {
  padding: 0 6px;
  border: 1px solid var(--line-strong);
  border-radius: var(--radius-mark);
  font-size: 11px;
  line-height: 18px;
  color: var(--ink-secondary);
  white-space: nowrap;
}
.fylld {
  border-color: transparent;
  color: var(--ink);
}
.votering {
  background: var(--markning-votering);
}
.reservation {
  background: var(--markning-reservation);
}
.oenighet {
  background: var(--markning-oenighet);
}
</style>
