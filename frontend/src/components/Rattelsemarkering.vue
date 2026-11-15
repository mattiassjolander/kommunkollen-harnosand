<script setup lang="ts">
// Markering för en uppgift som redaktionen har rättat (docs/design.md, Säkerhetsmarkeringar).
// Läsaren kan fälla ut vad den automatiska tolkningen sa och varför uppgiften rättades.
import { computed } from 'vue'
import { BEHANDLINGSTYPER, type Rattelsemarkering } from '../api'
import { datum, parti, rosttext } from '../format'

const props = defineProps<{ rattelse: Rattelsemarkering; falt: string }>()

function visa(v: unknown): string {
  if (v === null || v === undefined || (Array.isArray(v) && v.length === 0)) {
    return props.falt === 'parti' ? 'inget parti' : props.falt === 'typ' ? 'kunde inte klassas' : 'inget'
  }
  if (props.falt === 'parti') return parti(v as string)
  if (props.falt === 'typ') return BEHANDLINGSTYPER.find((t) => t.id === v)?.namn ?? String(v)
  if (props.falt === 'rost') return rosttext(v as 'ja' | 'nej' | 'avstar' | 'franvarande')
  if (Array.isArray(v)) return v.join(', ')
  return String(v)
}
const tolkat = computed(() => visa(props.rattelse.ursprungligt))
</script>

<template>
  <details class="rattelse" data-testid="rattad" :data-falt="falt">
    <summary>
      <span class="ikon" aria-hidden="true">✎</span>
      Rättad av redaktionen
    </summary>
    <div class="detaljer">
      <p>
        <span class="etikett">Tolkningen sa:</span> <span data-testid="ursprungligt">{{ tolkat }}</span>
      </p>
      <p><span class="etikett">Motivering:</span> {{ rattelse.motivering }}</p>
      <p class="datum">Publicerad {{ datum(rattelse.publicerad) }}</p>
    </div>
  </details>
</template>

<style scoped>
.rattelse {
  display: inline-block;
  font-size: 12px;
  color: var(--ink-secondary);
  vertical-align: baseline;
}
summary {
  cursor: pointer;
  display: inline-flex;
  align-items: center;
  gap: 6px;
  list-style: none;
}
summary::-webkit-details-marker {
  display: none;
}
.ikon {
  display: inline-flex;
  width: 16px;
  height: 16px;
  align-items: center;
  justify-content: center;
  border: 1px solid currentColor;
  border-radius: 50%;
  font-size: 10px;
}
.detaljer {
  margin-top: 6px;
  padding: 8px 12px;
  border-left: 2px solid var(--line);
  max-width: 70ch;
  white-space: pre-line;
}
.detaljer p {
  margin: 0 0 4px;
}
.etikett {
  font-weight: 600;
}
.datum {
  color: var(--ink-muted);
}
</style>
