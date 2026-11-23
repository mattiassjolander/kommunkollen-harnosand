<script setup lang="ts">
// Stat-kort: ett nyckeltals senaste värde, förändringen mot föregående år och källa.
// Förändringen visas neutralt, utan grönt/rött: om en ökning är bra beror på nyckeltalet
// och på vem som läser, och plattformen är partipolitiskt obunden.
import { computed } from 'vue'
import type { RouteLocationRaw } from 'vue-router'
import type { Nyckeltal } from '../api'
import { forandring, perPeriod, skillnad as skillnadMotRiket } from '../analys'
import { datum, procentforandring, siffra, tal, visningsskala } from '../format'
import Revisionsmarkering from './Revisionsmarkering.vue'

const props = defineProps<{
  nyckeltal: Nyckeltal
  lank: RouteLocationRaw
  /** En mening i klartext om vad måttet betyder (huvudtalen i ekonomivyn). */
  forklaring?: string
  /** Visas i stället för källans titel. */
  titel?: string
  /** Visa genomsnittet för riket samma år, när måttet har det (#82). */
  riket?: boolean
}>()

const serie = computed(() => props.nyckeltal.serie)
const skala = computed(() => visningsskala(serie.value?.matt.enhet ?? ''))
const skalad = (v: number | null) => (v === null ? null : v * skala.value.faktor)

// Senaste året med ett värde, och året före det.
const senaste = computed(() => {
  const punkter = (serie.value?.punkter ?? []).filter((p) => p.varde !== null)
  const nu = punkter[punkter.length - 1]
  if (!nu) return null
  const fore = serie.value!.punkter.find((p) => Number(p.period) === Number(nu.period) - 1) ?? null
  return {
    punkt: nu,
    varde: skalad(nu.varde)!,
    foreAr: String(Number(nu.period) - 1),
    f: forandring(skalad(fore?.varde ?? null), skalad(nu.varde), skala.value.enhet),
  }
})

const riket = computed(() => {
  if (!props.riket || !props.nyckeltal.riket || !senaste.value) return null
  const v = perPeriod(props.nyckeltal.riket).get(senaste.value.punkt.period) ?? null
  return v === null ? null : { varde: skalad(v)!, skillnad: senaste.value.varde - skalad(v)! }
})

const revision = computed(() => {
  const p = senaste.value?.punkt
  const [tidigare] = p?.historik ?? []
  return p && tidigare
    ? { tidigare: skalad(tidigare.varde), andrad: p.senast_andrad, kalla: serie.value!.matt.datakalla.titel }
    : null
})

const pil = (v: number) => (v > 0 ? '▲' : v < 0 ? '▼' : '■')
const skillnad = (v: number) => {
  const tecken = v > 0 ? '+' : v < 0 ? '−' : '±'
  const enhet = skala.value.enhet
  return enhet.includes('%')
    ? `${tecken}${siffra(Math.abs(v), enhet)} procentenheter`
    : `${tecken}${tal(Math.abs(v), enhet)}`
}

// "SCB (ResultKnN, post 120)" eller "Kolada (N03102)".
const beteckning = computed(() => {
  const delar = props.nyckeltal.id.split(':').slice(1)
  if (delar.length === 2) return `${delar[0]}, post ${delar[1]}`
  return /^[A-Z]\d+$/.test(delar[0] ?? '') ? delar[0] : null
})
</script>

<template>
  <article class="statkort" data-testid="statkort" :data-matt="nyckeltal.id">
    <h3>
      <RouterLink :to="lank">{{ titel ?? serie?.matt.titel ?? nyckeltal.id }}</RouterLink>
    </h3>
    <p v-if="forklaring" class="forklaring" data-testid="forklaring">{{ forklaring }}</p>
    <template v-if="senaste">
      <p class="varde">
        <span class="tal" data-testid="statvarde">{{ tal(senaste.varde, skala.enhet) }}</span>
        <Revisionsmarkering v-if="revision" :revision="revision" :nytt="senaste.varde" :enhet="skala.enhet" />
      </p>
      <p class="period">{{ senaste.punkt.period }}</p>
      <p v-if="senaste.f" class="forandring" data-testid="statforandring">
        <span class="pil" aria-hidden="true">{{ pil(senaste.f.skillnad) }}</span>
        <span class="tal">{{ skillnad(senaste.f.skillnad) }}</span>
        <span v-if="senaste.f.andel !== null" class="tal">({{ procentforandring(senaste.f.andel) }})</span>
        <span class="mot">mot {{ senaste.foreAr }}</span>
      </p>
      <p v-else class="forandring saknas">Uppgift saknas för {{ senaste.foreAr }}</p>
      <p v-if="riket" class="riket" data-testid="statriket">
        Riket: <span class="tal">{{ tal(riket.varde, skala.enhet) }}</span>
        <span class="mot">skillnad {{ skillnadMotRiket(riket.skillnad, skala.enhet) }}</span>
      </p>
    </template>
    <p v-else class="varde saknas">Uppgift saknas</p>
    <p v-if="serie" class="kallrad" data-testid="kallrad">
      Källa: <a :href="serie.matt.datakalla.url" target="_blank" rel="noopener">{{ serie.matt.datakalla.titel }}</a>
      {{ beteckning ? ` (${beteckning})` : '' }}
      <template v-if="nyckeltal.prisniva"> · {{ nyckeltal.prisniva }}</template>
      · Publicerad {{ datum(serie.matt.kallans_publicering) }}
    </p>
  </article>
</template>

<style scoped>
.statkort {
  background: var(--surface);
  border: 1px solid var(--line);
  border-radius: var(--radius);
  padding: 20px 24px;
  display: flex;
  flex-direction: column;
  min-width: 0;
}
h3 {
  font-size: 13px;
  font-weight: 600;
  color: var(--ink-secondary);
  margin: 0 0 8px;
}
h3 a {
  color: inherit;
  text-decoration: none;
}
h3 a:hover {
  color: var(--accent);
  text-decoration: underline;
}
.forklaring {
  font-size: 13px;
  color: var(--ink-secondary);
  margin: -4px 0 12px;
}
.varde {
  font-size: 32px;
  overflow-wrap: anywhere;
  font-weight: 600;
  line-height: 1.15;
  margin: 0;
  color: var(--ink);
  font-variant-numeric: proportional-nums;
}
.varde :deep(.reviderad) {
  font-size: 16px;
  vertical-align: top;
}
.period {
  font-size: 12px;
  color: var(--ink-muted);
  margin: 2px 0 12px;
}
.forandring {
  display: flex;
  flex-wrap: wrap;
  align-items: baseline;
  gap: 2px 6px;
  font-size: 13px;
  margin: 0 0 12px;
  color: var(--ink);
}
.pil {
  font-size: 10px;
  color: var(--ink-secondary);
}
.riket {
  font-size: 13px;
  margin: -4px 0 12px;
  display: flex;
  flex-wrap: wrap;
  gap: 2px 6px;
}
.mot {
  color: var(--ink-muted);
}
.saknas {
  color: var(--ink-muted);
  font-style: italic;
}
.varde.saknas {
  font-size: 15px;
  font-weight: 400;
  margin-bottom: 12px;
}
.kallrad {
  font-size: 12px;
  color: var(--ink-muted);
  margin: auto 0 0;
}
.kallrad a {
  color: inherit;
}
</style>
