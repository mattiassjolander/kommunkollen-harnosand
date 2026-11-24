<script setup lang="ts">
// Ett led i sammansättningen (#65): kön och åldersgrupper totalt och per parti, som staplar på 100 procent med
// de röstberättigade som referens, och samma siffror som tabell och CSV. "Uppgift saknas" är en egen grupp.
import { computed } from 'vue'
import type { Sammansattning, Sammansattningsled, Sammansattningsmatt } from '../api'
import { datum, parti as partitext, tal } from '../format'
import Partimarkering from './Partimarkering.vue'

const props = defineProps<{
  id: string
  rubrik: string
  beskrivning: string
  led: Sammansattningsled
  referens: Sammansattning['referens']
  aldersgrupper: string[]
  period: string
  /** Vad en post är: "personer", eller "tjänstgöringar" för de tjänstgörande. */
  enhet?: string
}>()

const enhet = computed(() => props.enhet ?? 'personer')
const ALDERSFARG = ['var(--seq-1)', 'var(--seq-2)', 'var(--seq-3)', 'var(--seq-4)']

interface Rad {
  nyckel: string
  etikett: string
  parti: string | null
  m: Sammansattningsmatt
}
const rader = computed<Rad[]>(() => [
  { nyckel: 'totalt', etikett: 'Totalt', parti: null, m: props.led.totalt },
  ...props.led.per_parti.map((p) => ({
    nyckel: p.parti,
    etikett: partitext(partinamn(p.parti)),
    parti: p.parti,
    m: p,
  })),
])

function procent(n: number, av: number): string {
  return av ? `${Math.round((n / av) * 100)} %` : '–'
}
function bredd(n: number, av: number): string {
  return av ? `${(n / av) * 100}%` : '0'
}
function partinamn(p: string): string | null {
  return p === '?' ? null : p
}

const kallrad = computed(() =>
  props.led.kallor
    .filter((k) => k)
    .map((k) => `${k!.titel}${k!.stampel ? ` (${k!.stampel})` : ''}, hämtad ${datum(k!.hamtad)}`)
    .join(' · '),
)

const csv = computed(() => {
  const huvud = ['Grupp', 'Antal', 'Kvinnor', 'Män', 'Kön saknas', 'Medelålder', ...props.aldersgrupper, 'Ålder saknas']
  const rad = (r: Rad) => [
    r.etikett,
    r.m.antal,
    r.m.kvinnor,
    r.m.man,
    r.m.kon_saknas,
    r.m.medelalder ?? '',
    ...props.aldersgrupper.map((g) => r.m.aldersgrupper[g] ?? 0),
    r.m.aldersgrupper.saknas ?? 0,
  ]
  const text = [huvud, ...rader.value.map(rad)].map((r) => r.join(';')).join('\n')
  return `data:text/csv;charset=utf-8,${encodeURIComponent('﻿' + text)}`
})
</script>

<template>
  <section class="kort" :aria-labelledby="`${id}-rubrik`" :data-testid="`led-${id}`">
    <div class="rubrikrad">
      <h2 :id="`${id}-rubrik`">{{ rubrik }}</h2>
      <a :href="csv" :download="`sammansattning-${id}-${period}.csv`" class="knapp" data-testid="csv">Ladda ned CSV</a>
    </div>
    <p class="beskrivning">{{ beskrivning }}</p>

    <ul class="forklaring" aria-label="Teckenförklaring">
      <li><span class="ruta" style="background: var(--series-1)" />Kvinnor</li>
      <li><span class="ruta" style="background: var(--series-2)" />Män</li>
      <li><span class="ruta saknas-ruta" />Uppgift saknas</li>
      <li v-for="(g, i) in aldersgrupper" :key="g"><span class="ruta" :style="{ background: ALDERSFARG[i] }" />{{ g }} år</li>
    </ul>

    <div class="staplar" role="table" :aria-label="`${rubrik}, kön och ålder`">
      <div class="stapelrad huvud" role="row">
        <span role="columnheader">Grupp</span>
        <span role="columnheader">Kön</span>
        <span role="columnheader">Ålder</span>
      </div>
      <div
        v-for="r in rader"
        :key="r.nyckel"
        class="stapelrad"
        role="row"
        data-testid="sammansattningsrad"
        :data-grupp="r.nyckel"
      >
        <span role="rowheader" class="grupp">
          <strong v-if="!r.parti">Totalt</strong>
          <Partimarkering v-else :parti="partinamn(r.parti)" />
          <span class="antal">{{ tal(r.m.antal) }}</span>
        </span>
        <span role="cell" class="stapel">
          <span
            v-if="r.m.kvinnor"
            class="del"
            :style="{ width: bredd(r.m.kvinnor, r.m.antal), background: 'var(--series-1)' }"
            :title="`Kvinnor: ${tal(r.m.kvinnor)} av ${tal(r.m.antal)} ${enhet} (${procent(r.m.kvinnor, r.m.antal)}), ${period}`"
          />
          <span
            v-if="r.m.man"
            class="del"
            :style="{ width: bredd(r.m.man, r.m.antal), background: 'var(--series-2)' }"
            :title="`Män: ${tal(r.m.man)} av ${tal(r.m.antal)} ${enhet} (${procent(r.m.man, r.m.antal)}), ${period}`"
          />
          <span
            v-if="r.m.kon_saknas"
            class="del saknas-ruta"
            :style="{ width: bredd(r.m.kon_saknas, r.m.antal) }"
            :title="`Uppgift saknas: ${tal(r.m.kon_saknas)} av ${tal(r.m.antal)} ${enhet}`"
            data-testid="kon-saknas"
          />
        </span>
        <span role="cell" class="stapel">
          <span
            v-for="(g, i) in aldersgrupper"
            v-show="r.m.aldersgrupper[g]"
            :key="g"
            class="del"
            :style="{ width: bredd(r.m.aldersgrupper[g] ?? 0, r.m.antal), background: ALDERSFARG[i] }"
            :title="`${g} år: ${tal(r.m.aldersgrupper[g] ?? 0)} av ${tal(r.m.antal)} ${enhet} (${procent(r.m.aldersgrupper[g] ?? 0, r.m.antal)}), ${period}`"
          />
          <span
            v-if="r.m.aldersgrupper.saknas"
            class="del saknas-ruta"
            :style="{ width: bredd(r.m.aldersgrupper.saknas, r.m.antal) }"
            :title="`Uppgift saknas: ${tal(r.m.aldersgrupper.saknas)} av ${tal(r.m.antal)} ${enhet}`"
          />
        </span>
      </div>
      <div v-if="referens" class="stapelrad referens" role="row" data-testid="referensrad">
        <span role="rowheader" class="grupp">Röstberättigade {{ referens.valar }}</span>
        <span role="cell" class="stapel">
          <span
            class="del"
            :style="{ width: `${referens.andel_kvinnor * 100}%`, background: 'var(--series-1)' }"
            :title="`Kvinnor: ${procent(referens.andel_kvinnor * referens.antal, referens.antal)} av de röstberättigade`"
          />
          <span
            class="del"
            :style="{ width: `${referens.andel_man * 100}%`, background: 'var(--series-2)' }"
            :title="`Män: ${procent(referens.andel_man * referens.antal, referens.antal)} av de röstberättigade`"
          />
        </span>
        <span role="cell" class="stapel">
          <span
            v-for="(g, i) in aldersgrupper"
            :key="g"
            class="del"
            :style="{ width: bredd(referens.aldersgrupper[g] ?? 0, referens.antal), background: ALDERSFARG[i] }"
            :title="`${g} år: ${procent(referens.aldersgrupper[g] ?? 0, referens.antal)} av de röstberättigade`"
          />
        </span>
      </div>
    </div>

    <details class="tabellvy">
      <summary>Visa som tabell</summary>
      <div class="rulla">
        <table class="tabell" data-testid="sammansattningstabell">
          <thead>
            <tr>
              <th scope="col">Grupp</th>
              <th scope="col" class="num">Antal</th>
              <th scope="col" class="num">Kvinnor</th>
              <th scope="col" class="num">Män</th>
              <th scope="col" class="num">Kön saknas</th>
              <th scope="col" class="num">Medelålder</th>
              <th v-for="g in aldersgrupper" :key="g" scope="col" class="num">{{ g }}</th>
              <th scope="col" class="num">Ålder saknas</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="r in rader" :key="r.nyckel" :data-grupp="r.nyckel">
              <th scope="row">{{ r.etikett }}</th>
              <td class="num">{{ tal(r.m.antal) }}</td>
              <td class="num">{{ tal(r.m.kvinnor) }} ({{ procent(r.m.kvinnor, r.m.antal) }})</td>
              <td class="num">{{ tal(r.m.man) }} ({{ procent(r.m.man, r.m.antal) }})</td>
              <td class="num">{{ tal(r.m.kon_saknas) }}</td>
              <td class="num">{{ r.m.medelalder === null ? 'Uppgift saknas' : `${tal(r.m.medelalder)} år` }}</td>
              <td v-for="g in aldersgrupper" :key="g" class="num">{{ tal(r.m.aldersgrupper[g] ?? 0) }}</td>
              <td class="num">{{ tal(r.m.aldersgrupper.saknas ?? 0) }}</td>
            </tr>
          </tbody>
        </table>
      </div>
    </details>

    <p class="kallrad" data-testid="kallrad">
      Källa: {{ kallrad || 'Uppgift saknas' }}<template v-if="led.personer !== undefined">
        · {{ tal(led.personer) }} personer vid {{ tal(led.sammantraden ?? 0) }} sammanträden</template
      ><template v-if="referens">
        · Referens: röstberättigade på valdagen {{ referens.valar }}, Valmyndigheten</template
      >
    </p>
  </section>
</template>

<style scoped>
.kort {
  background: var(--surface);
  border: 1px solid var(--line);
  border-radius: var(--radius);
  padding: 16px 24px;
  margin-bottom: 16px;
}
.rubrikrad {
  display: flex;
  justify-content: space-between;
  align-items: baseline;
  gap: 12px;
}
h2 {
  font-size: 15px;
  margin: 0 0 4px;
}
.beskrivning {
  font-size: 13px;
  color: var(--ink-secondary);
  margin: 0 0 8px;
  max-width: 80ch;
}
.knapp {
  font-size: 13px;
  color: var(--accent);
}
.forklaring {
  list-style: none;
  display: flex;
  flex-wrap: wrap;
  gap: 4px 16px;
  padding: 0;
  margin: 0 0 8px;
  font-size: 12px;
  color: var(--ink-secondary);
}
.forklaring li {
  display: inline-flex;
  align-items: center;
  gap: 6px;
}
.ruta {
  width: 10px;
  height: 10px;
  border-radius: 2px;
  display: inline-block;
}
.saknas-ruta {
  background: repeating-linear-gradient(45deg, var(--ink-muted) 0 2px, transparent 2px 5px);
}
.staplar {
  display: grid;
  gap: 4px;
  font-size: 13px;
}
.stapelrad {
  display: grid;
  grid-template-columns: minmax(120px, 160px) 1fr 1fr;
  gap: 12px;
  align-items: center;
}
.stapelrad.huvud {
  color: var(--ink-muted);
  font-size: 12px;
}
.stapelrad.referens {
  border-top: 1px solid var(--line);
  padding-top: 4px;
  color: var(--ink-secondary);
}
.grupp {
  display: flex;
  justify-content: space-between;
  gap: 8px;
}
.antal {
  color: var(--ink-muted);
  font-variant-numeric: tabular-nums;
}
.stapel {
  display: flex;
  gap: 2px;
  height: 14px;
}
.del {
  display: block;
  height: 100%;
  border-radius: 2px;
}
.tabellvy {
  margin-top: 12px;
  font-size: 13px;
}
.tabellvy summary {
  cursor: pointer;
  color: var(--accent);
}
.rulla {
  overflow-x: auto;
}
.tabell {
  border-collapse: collapse;
  width: 100%;
  font-size: 13px;
  margin-top: 8px;
}
.tabell th,
.tabell td {
  text-align: left;
  padding: 6px 8px;
  border-bottom: 1px solid var(--line);
  white-space: nowrap;
}
.tabell .num {
  text-align: right;
  font-variant-numeric: tabular-nums;
}
.tabell thead th {
  color: var(--ink-secondary);
  font-weight: 600;
}
.kallrad {
  font-size: 12px;
  color: var(--ink-muted);
  margin: 12px 0 0;
}
</style>
