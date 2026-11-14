<script setup lang="ts">
import { computed } from 'vue'
import type { Nyckeltal } from '../api'
import { csv, forandring, laddaNer, mandatperioder } from '../analys'
import { procentforandring, siffra, tal, visningsskala } from '../format'
import Kallrad from './Kallrad.vue'
import Stapeldiagram from './Stapeldiagram.vue'

const props = defineProps<{
  nyckeltal: Nyckeltal
  franAr: number
  tillAr: number
  vy: 'diagram' | 'tabell'
  /** Två år att jämföra, eller null. */
  jamforelse: [number, number] | null
}>()
const emit = defineEmits<{ vy: ['diagram' | 'tabell'] }>()

const serie = computed(() => props.nyckeltal.serie)
const skala = computed(() => visningsskala(serie.value?.matt.enhet ?? ''))
const punkter = computed(() =>
  (serie.value?.punkter ?? [])
    .filter((p) => Number(p.period) >= props.franAr && Number(p.period) <= props.tillAr)
    .map((p) => ({ period: p.period, varde: p.varde === null ? null : p.varde * skala.value.faktor })),
)
const perioder = computed(() => mandatperioder(props.franAr, props.tillAr))

// Jämförelsen gäller de valda åren oavsett visad period, i visningsenheten.
const jamforelse = computed(() => {
  if (!props.jamforelse || !serie.value) return null
  const [a, b] = props.jamforelse
  const varde = (ar: number) => {
    const p = serie.value!.punkter.find((p) => Number(p.period) === ar)
    return p && p.varde !== null ? p.varde * skala.value.faktor : null
  }
  return { a, b, f: forandring(varde(a), varde(b), skala.value.enhet) }
})
// Förändringen med tecken: "+12,3 mnkr", för nyckeltal i procent "−2,1 procentenheter".
const skillnad = (v: number) => {
  const tecken = v > 0 ? '+' : v < 0 ? '−' : ''
  const enhet = skala.value.enhet
  return enhet.includes('%')
    ? `${tecken}${siffra(Math.abs(v), enhet)} procentenheter`
    : `${tecken}${tal(Math.abs(v), enhet)}`
}

function exportera() {
  const id = props.nyckeltal.id.replace(/[^\w]+/g, '-')
  laddaNer(`kommunkollen-${id}-${props.franAr}-${props.tillAr}.csv`, csv([props.nyckeltal], props.franAr, props.tillAr))
}

const kallnamn = computed(() => (serie.value ? `Källa: ${serie.value.matt.datakalla.titel}` : ''))
</script>

<template>
  <section class="kort" data-testid="nyckeltal" :data-matt="nyckeltal.id">
    <div class="huvud">
      <h3>{{ serie?.matt.titel ?? nyckeltal.id }}</h3>
      <div v-if="serie" class="vaxel" role="group" :aria-label="`Visa ${serie.matt.titel} som`">
        <button type="button" :aria-pressed="vy === 'diagram'" @click="emit('vy', 'diagram')">Diagram</button>
        <button type="button" :aria-pressed="vy === 'tabell'" @click="emit('vy', 'tabell')">Tabell</button>
      </div>
    </div>

    <p v-if="!serie" class="beskrivning">Uppgift saknas. Ingen insamling har hämtat det här nyckeltalet än.</p>
    <template v-else>
      <p class="beskrivning">{{ serie.matt.beskrivning }}</p>
      <p
        v-if="jamforelse"
        class="jamforelse"
        :class="{ stor: jamforelse.f?.stor }"
        data-testid="jamforelse"
        :data-stor="jamforelse.f?.stor ? 'ja' : 'nej'"
      >
        <span class="period">{{ jamforelse.a }}–{{ jamforelse.b }}:</span>
        <template v-if="jamforelse.f">
          <strong class="tal">{{ skillnad(jamforelse.f.skillnad) }}</strong>
          <span v-if="jamforelse.f.andel !== null" class="tal">({{ procentforandring(jamforelse.f.andel) }})</span>
          <span class="sekundar tal">{{ tal(jamforelse.f.fore, skala.enhet) }} → {{ tal(jamforelse.f.efter, skala.enhet) }}</span>
          <span v-if="jamforelse.f.stor" class="markering">Större förändring</span>
        </template>
        <span v-else class="saknas">Uppgift saknas för något av åren</span>
      </p>
      <p v-if="!punkter.length" class="beskrivning">Uppgift saknas för de valda åren.</p>
      <Stapeldiagram
        v-else-if="vy === 'diagram'"
        :punkter="punkter"
        :enhet="skala.enhet"
        :kalla="kallnamn"
        :mandatperioder="perioder"
      />
      <table v-else class="tabell">
        <caption class="dold">{{ serie.matt.titel }}</caption>
        <thead>
          <tr>
            <th scope="col">År</th>
            <th scope="col" class="hoger">{{ skala.enhet }}</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="p in punkter" :key="p.period">
            <td class="tal">{{ p.period }}</td>
            <td class="tal hoger" :class="{ saknas: p.varde === null }">{{ siffra(p.varde, skala.enhet) }}</td>
          </tr>
        </tbody>
      </table>
      <div class="fot">
        <Kallrad :serie="serie" :perioder="punkter.map((p) => p.period)" :prisniva="nyckeltal.prisniva" />
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
.beskrivning {
  color: var(--ink-secondary);
  margin: 4px 0 16px;
  max-width: 70ch;
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
.jamforelse {
  display: flex;
  flex-wrap: wrap;
  align-items: baseline;
  gap: 4px 8px;
  margin: 0 0 16px;
  padding: 8px 12px;
  border-left: 3px solid var(--line-strong);
  background: var(--page);
  font-size: 13px;
}
.jamforelse.stor {
  border-left-color: var(--accent);
}
.jamforelse .period,
.sekundar {
  color: var(--ink-muted);
}
.markering {
  font-size: 12px;
  font-weight: 600;
  color: var(--accent);
  border: 1px solid var(--accent);
  border-radius: 999px;
  padding: 0 8px;
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
