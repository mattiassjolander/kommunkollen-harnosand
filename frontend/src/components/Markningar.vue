<script setup lang="ts">
// Märkningarna på en behandling eller ett ärende som små chips (docs/design.md, Märkningar, #162, #174).
// Votering, Reservation och Oenighet har var sin ljusa fyllning med mörk text i samma kulör, resten är konturchips.
// Varje chip har text, så färgen bär aldrig betydelse ensam. Chipet länkar till Sök med märkningen förvald.
import { MARKNINGAR, type Markning } from '../api'

withDefaults(
  defineProps<{
    markningar: Markning[]
    /** Chipsen länkar till Sök. Av där de står i en knapp eller en annan länk, eftersom länkar inte får nästlas. */
    lankar?: boolean
  }>(),
  { lankar: true },
)

const FYLLDA = new Set(['votering', 'reservation', 'oenighet'])
const NAMN = new Map(MARKNINGAR.map((m) => [m.id, m.namn]))

function titel(m: Markning, lankar: boolean): string | undefined {
  const namn = NAMN.get(m.id) ?? m.text
  const antal = m.antal && m.antal > 1 ? `${namn} vid ${m.antal} behandlingar` : undefined
  if (!lankar) return antal
  const sok = `Sök alla med märkningen ${namn.toLowerCase()}`
  return antal ? `${antal}. ${sok}` : sok
}
</script>

<template>
  <ul v-if="markningar.length" class="markningar" aria-label="Märkningar" data-testid="markningar">
    <li v-for="m in markningar" :key="m.id">
      <RouterLink
        v-if="lankar"
        :to="{ path: '/sok', query: { markning: m.id } }"
        class="chip"
        :class="[FYLLDA.has(m.id) ? `fylld ${m.id}` : 'kontur']"
        :title="titel(m, true)"
        data-testid="markning"
        :data-markning="m.id"
      >
        {{ m.text }}
      </RouterLink>
      <span
        v-else
        class="chip"
        :class="[FYLLDA.has(m.id) ? `fylld ${m.id}` : 'kontur']"
        :title="titel(m, false)"
        data-testid="markning"
        :data-markning="m.id"
      >
        {{ m.text }}
      </span>
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
.markningar li {
  display: flex;
}
.chip {
  display: inline-block;
  padding: 0 6px;
  border: 1px solid var(--line-strong);
  border-radius: var(--radius-mark);
  font-size: 11px;
  font-weight: 400;
  line-height: 18px;
  color: var(--ink);
  text-decoration: none;
  white-space: nowrap;
}
a.chip:hover {
  border-color: currentColor;
  text-decoration: underline;
}
.fylld {
  border-color: transparent;
  font-weight: 500;
}
.votering {
  background: var(--markning-votering);
  color: var(--markning-votering-text);
}
.reservation {
  background: var(--markning-reservation);
  color: var(--markning-reservation-text);
}
.oenighet {
  background: var(--markning-oenighet);
  color: var(--markning-oenighet-text);
}
</style>
