<script setup lang="ts">
// Ett nyckeltal vars definition källan har bytt (metodbyte, #66 och #67). Den gamla och den nya definitionen
// visas som separata linjer och slås aldrig ihop. Ett saknat värde bryter linjen och visas som "Uppgift saknas".
import { computed } from 'vue'
import type { Metodbyte, Nyckeltal } from '../api'
import { csv, laddaNer, perPeriod } from '../analys'
import { siffra } from '../format'
import Kallrad from './Kallrad.vue'
import Linjediagram from './Linjediagram.vue'

const props = defineProps<{
  titel: string
  metodbyte: Metodbyte
  /** Nyckeltalen i metodbytet, i valfri ordning. */
  nyckeltal: Nyckeltal[]
  franAr: number
  tillAr: number
  vy: 'diagram' | 'tabell'
  producent?: string
}>()
const emit = defineEmits<{ vy: ['diagram' | 'tabell'] }>()

// Serierna i metodbytets ordning (den gamla definitionen först), med riket när Kolada har det.
const serier = computed(() =>
  props.metodbyte.serier.flatMap((m) => {
    const n = props.nyckeltal.find((n) => n.id === m.id)
    if (!n?.serie) return []
    return [
      { namn: m.namn, serie: n.serie, varden: perPeriod(n.serie) },
      ...(n.riket ? [{ namn: `${m.namn}, riket`, serie: n.riket, varden: perPeriod(n.riket) }] : []),
    ]
  }),
)
const ar = computed(() => {
  const alla = new Set<number>()
  for (const s of serier.value)
    for (const [period, v] of s.varden) {
      const a = Number(period)
      if (v !== null && a >= props.franAr && a <= props.tillAr) alla.add(a)
    }
  return [...alla].sort((a, b) => a - b)
})
const enhet = computed(() => serier.value[0]?.serie.matt.enhet ?? '')
const diagramserier = computed(() =>
  serier.value.map((s) => ({
    namn: s.namn,
    punkter: ar.value.map((a) => ({ ar: a, varde: s.varden.get(String(a)) ?? null })),
  })),
)
const kallnamn = computed(() => {
  const kalla = serier.value[0]?.serie.matt.datakalla.titel ?? ''
  return `Källa: ${props.producent ? `${props.producent}/` : ''}${kalla}`
})

function exportera() {
  laddaNer(`kommunkollen-metodbyte-${props.franAr}-${props.tillAr}.csv`, csv(props.nyckeltal, props.franAr, props.tillAr, true))
}
</script>

<template>
  <section class="kort" data-testid="metodbyte">
    <div class="huvud">
      <h3>{{ titel }}</h3>
      <div v-if="ar.length" class="vaxel" role="group" :aria-label="`Visa ${titel} som`">
        <button type="button" :aria-pressed="vy === 'diagram'" @click="emit('vy', 'diagram')">Diagram</button>
        <button type="button" :aria-pressed="vy === 'tabell'" @click="emit('vy', 'tabell')">Tabell</button>
      </div>
    </div>
    <p class="metodbyte">
      <span class="markering">Metodbyte {{ metodbyte.ar }}</span>
      <span data-testid="metodbyte-text">{{ metodbyte.text }}</span>
    </p>

    <p v-if="!serier.length" class="beskrivning">Uppgift saknas. Ingen insamling har hämtat de här nyckeltalen än.</p>
    <p v-else-if="!ar.length" class="beskrivning">Uppgift saknas för de valda åren.</p>
    <template v-else>
      <Linjediagram
        v-if="vy === 'diagram'"
        :serier="diagramserier"
        :enhet="enhet"
        :kalla="kallnamn"
        :etikett="`${titel}: ${serier.map((s) => s.namn).join(' och ')}, ${ar[0]}–${ar[ar.length - 1]}`"
      />
      <table v-else class="tabell">
        <caption class="dold">{{ titel }}</caption>
        <thead>
          <tr>
            <th scope="col">År</th>
            <th v-for="s in serier" :key="s.namn" scope="col" class="hoger">{{ s.namn }}</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="a in ar" :key="a">
            <td class="tal">{{ a }}</td>
            <td
              v-for="s in serier"
              :key="s.namn"
              class="tal hoger"
              :class="{ saknas: (s.varden.get(String(a)) ?? null) === null }"
            >
              {{ siffra(s.varden.get(String(a)) ?? null, enhet) }}
            </td>
          </tr>
        </tbody>
      </table>
      <div class="fot">
        <div>
          <Kallrad
            v-for="s in serier.filter((s) => s.serie.omrade !== '0000')"
            :key="s.namn"
            :serie="s.serie"
            :perioder="s.serie.punkter.map((p) => p.period).filter((p) => Number(p) >= franAr && Number(p) <= tillAr)"
            :producent="producent"
          />
        </div>
        <button type="button" class="csv" data-testid="csv" @click="exportera">CSV</button>
      </div>
    </template>
  </section>
</template>

<style scoped>
.kort {
  background: var(--surface);
  border: 1px solid var(--line);
  border-radius: var(--radius);
  padding: 24px;
  min-width: 0;
}
.huvud {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 12px;
}
.metodbyte {
  display: flex;
  flex-wrap: wrap;
  align-items: baseline;
  gap: 4px 8px;
  margin: 4px 0 16px;
  padding: 8px 12px;
  border-left: 3px solid var(--line-strong);
  background: var(--page);
  font-size: 13px;
  color: var(--ink-secondary);
  max-width: 80ch;
}
.markering {
  font-size: 12px;
  font-weight: 600;
  color: var(--ink);
  border: 1px solid var(--line-strong);
  border-radius: 999px;
  padding: 0 8px;
  white-space: nowrap;
}
.beskrivning {
  color: var(--ink-secondary);
  margin: 4px 0 16px;
}
.vaxel {
  display: inline-flex;
  border: 1px solid var(--line-strong);
  border-radius: var(--radius);
  overflow: hidden;
  flex-shrink: 0;
}
.vaxel button {
  font: inherit;
  font-size: 12px;
  padding: 4px 10px;
  border: 0;
  background: var(--surface-raised);
  color: var(--ink-secondary);
  cursor: pointer;
}
.vaxel button + button {
  border-left: 1px solid var(--line-strong);
}
.vaxel button[aria-pressed='true'] {
  background: var(--accent-wash);
  color: var(--accent);
  font-weight: 600;
}
.fot {
  display: flex;
  justify-content: space-between;
  align-items: flex-end;
  gap: 12px;
}
.csv {
  flex-shrink: 0;
  font: inherit;
  font-size: 12px;
  padding: 2px 8px;
  border: 1px solid var(--line-strong);
  border-radius: var(--radius);
  background: var(--surface-raised);
  color: var(--ink-secondary);
  cursor: pointer;
}
.csv:hover {
  background: var(--accent-wash);
}
.tabell {
  border-collapse: collapse;
  font-size: 13px;
  min-width: 240px;
}
.tabell th,
.tabell td {
  padding: 4px 12px 4px 0;
  border-bottom: 1px solid var(--line);
  text-align: left;
}
.tabell th {
  color: var(--ink-secondary);
  font-weight: 600;
}
.hoger {
  text-align: right !important;
}
.saknas {
  color: var(--ink-muted);
  font-style: italic;
}
.dold {
  position: absolute;
  width: 1px;
  height: 1px;
  overflow: hidden;
  clip: rect(0 0 0 0);
}
</style>
