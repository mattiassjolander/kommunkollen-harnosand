<script setup lang="ts">
// Statistik över protokollen (#44): behandlingar per år, organ och behandlingstyp. Organ och
// årsintervall speglas i URL:en, så att en vy går att dela (design.md, Filter).
import { computed, inject, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import {
  EjInloggad,
  hamtaBehandlingsstatistik,
  hamtaOrgan,
  type Behandlingsstatistik,
  type Organ,
} from '../../api'
import { sammantradesdatum, tal } from '../../format'
import PolitikFlikar from '../../components/PolitikFlikar.vue'

const route = useRoute()
const router = useRouter()
const utloggad = inject<() => void>('utloggad', () => {})

function fraga(namn: string) {
  return computed<string>({
    get: () => (typeof route.query[namn] === 'string' ? (route.query[namn] as string) : ''),
    set: (v) => router.replace({ query: { ...route.query, [namn]: v || undefined } }),
  })
}
const valtOrgan = fraga('organ')
const fran = fraga('fran')
const till = fraga('till')

const organ = ref<Organ[]>([])
const s = ref<Behandlingsstatistik | null>(null)
const laddar = ref(true)
const fel = ref<string | null>(null)
const omvant = computed(() => !!fran.value && !!till.value && Number(fran.value) > Number(till.value))

async function ladda() {
  if (omvant.value) return
  laddar.value = true
  fel.value = null
  try {
    s.value = await hamtaBehandlingsstatistik(fran.value, till.value, valtOrgan.value || undefined)
  } catch (e) {
    if (e instanceof EjInloggad) return utloggad()
    fel.value = e instanceof Error ? e.message : String(e)
  } finally {
    laddar.value = false
  }
}
onMounted(async () => {
  try {
    organ.value = await hamtaOrgan()
  } catch (e) {
    if (e instanceof EjInloggad) return utloggad()
  }
  await ladda()
})
watch([valtOrgan, fran, till], ladda)

// Valda år i filtret: URL:en, annars det API:t valde (hela arkivet).
const franAr = computed({ get: () => fran.value || String(s.value?.fran ?? ''), set: (v) => (fran.value = v) })
const tillAr = computed({ get: () => till.value || String(s.value?.till ?? ''), set: (v) => (till.value = v) })
const intervall = computed(() => (s.value ? (s.value.fran === s.value.till ? `${s.value.fran}` : `${s.value.fran}–${s.value.till}`) : ''))

// Typerna i fast ordning med fast färg (design.md, Diagram). "Kunde inte klassas" är neutral grå.
const typer = computed(() =>
  (s.value?.typer ?? []).map((t, i) => ({ ...t, farg: t.id === 'okand' ? 'var(--ink-muted)' : `var(--series-${i + 1})` })),
)
const NYCKELTAL = ['beslut', 'forslag', 'motion', 'medborgarforslag', 'information'] as const

// Diagrammet: en stapel per år, med alla valda organ sammanräknade och typerna staplade.
const perAr = computed(() => {
  const ar = new Map<number, Record<string, number>>()
  for (const r of s.value?.rader ?? []) {
    const a = ar.get(r.ar) ?? {}
    for (const [t, n] of Object.entries(r.antal)) a[t] = (a[t] ?? 0) + n
    ar.set(r.ar, a)
  }
  const alla = s.value ? Array.from({ length: s.value.till - s.value.fran + 1 }, (_, i) => s.value!.fran + i) : []
  return alla.map((a) => ({ ar: a, antal: ar.get(a) ?? {} }))
})
const B = 720
const H = 260
const M = { top: 12, right: 16, bottom: 28, left: 48 }
const maxSumma = computed(() => Math.max(1, ...perAr.value.map((p) => Object.values(p.antal).reduce((x, y) => x + y, 0))))
const steg = computed(() => {
  const ra = maxSumma.value / 4
  const pot = 10 ** Math.floor(Math.log10(ra || 1))
  const f = ra / pot
  return (f <= 1 ? 1 : f <= 2 ? 2 : f <= 5 ? 5 : 10) * pot
})
const yMax = computed(() => Math.ceil(maxSumma.value / steg.value) * steg.value)
const y = (v: number) => M.top + (1 - v / yMax.value) * (H - M.top - M.bottom)
const ticks = computed(() => Array.from({ length: Math.round(yMax.value / steg.value) + 1 }, (_, i) => i * steg.value))
const band = computed(() => (B - M.left - M.right) / Math.max(perAr.value.length, 1))
const stapelB = computed(() => Math.min(56, band.value * 0.6))
const segment = computed(() =>
  perAr.value.flatMap((p, i) => {
    let bas = 0
    const x = M.left + band.value * i + (band.value - stapelB.value) / 2
    const delar = typer.value.filter((t) => (p.antal[t.id] ?? 0) > 0)
    return delar.map((t, j) => {
      const n = p.antal[t.id]
      const y0 = y(bas)
      bas += n
      const y1 = y(bas)
      // 2 px mellanrum mellan segmenten, och 4 px rundning bara på stapelns översta del.
      return { ar: p.ar, typ: t, n, x, y: y1, h: Math.max(0, y0 - y1 - (j > 0 ? 2 : 0)), topp: j === delar.length - 1 }
    })
  }),
)
const hover = ref<{ ar: number; namn: string; n: number; x: number; y: number } | null>(null)

// Tabellvy och CSV-export (design.md, Diagram).
function csv(): string {
  if (!s.value) return ''
  const huvud = ['År', 'Organ', 'Sammanträden', 'Behandlingar', ...typer.value.map((t) => t.namn)]
  const rader = s.value.rader.map((r) => [r.ar, r.organ.namn, r.sammantraden, r.behandlingar, ...typer.value.map((t) => r.antal[t.id])])
  return [huvud, ...rader].map((r) => r.map((v) => `"${String(v).replace(/"/g, '""')}"`).join(';')).join('\n')
}
const csvLank = computed(() => `data:text/csv;charset=utf-8,${encodeURIComponent('﻿' + csv())}`)
const ofullstandigt = computed(
  () => !!s.value && (s.value.underlag.ej_tolkade.length > 0 || s.value.underlag.paragrafprotokoll.length > 0),
)
</script>

<template>
  <header class="vyhuvud">
    <h1>Politik och beslut</h1>
    <p class="ingress">
      Hur många behandlingar protokollen innehåller, per år, organ och typ. Typen läses ut automatiskt ur rubriken och
      beslutet, och redaktionen kan rätta den.
    </p>
  </header>
  <PolitikFlikar />

  <div class="filter" role="group" aria-label="Filter">
    <label>
      Organ
      <select v-model="valtOrgan" data-testid="filter-organ">
        <option value="">Alla organ</option>
        <option v-for="o in organ" :key="o.id" :value="o.id">{{ o.namn }}</option>
      </select>
    </label>
    <label>
      Från år
      <select v-model="franAr" data-testid="filter-fran">
        <option v-for="a in s?.tillgangliga_ar ?? []" :key="a" :value="String(a)">{{ a }}</option>
      </select>
    </label>
    <label>
      Till år
      <select v-model="tillAr" data-testid="filter-till">
        <option v-for="a in s?.tillgangliga_ar ?? []" :key="a" :value="String(a)">{{ a }}</option>
      </select>
    </label>
  </div>

  <p v-if="omvant" class="fel" role="alert" data-testid="omvant">Startåret kan inte vara efter slutåret.</p>
  <p v-else-if="fel" class="fel" role="alert">{{ fel }}</p>
  <p v-else-if="laddar && !s">Hämtar statistik…</p>
  <template v-else-if="s">
    <p class="markering" role="note" data-testid="automatiskt-tolkad">
      <span class="ikon" aria-hidden="true">⚙</span>
      Automatiskt tolkad, ej granskad. Typen avgörs med regler utifrån rubrik och beslut.
    </p>

    <section class="nyckeltal" aria-label="Summa för perioden" data-testid="nyckeltal">
      <div v-for="id in NYCKELTAL" :key="id" class="tal" :data-typ="id">
        <span class="varde">{{ tal(s.summa.antal[id]) }}</span>
        <span class="etikett">{{ s.typer.find((t) => t.id === id)?.namn }}</span>
      </div>
      <div class="tal">
        <span class="varde">{{ tal(s.summa.sammantraden) }}</span>
        <span class="etikett">Sammanträden</span>
      </div>
    </section>

    <section class="kort" aria-labelledby="diagram-rubrik">
      <h2 id="diagram-rubrik">Behandlingar per år och typ, {{ intervall }}{{ s.organ ? `, ${s.organ.namn}` : '' }}</h2>
      <ul class="forklaring" data-testid="teckenforklaring">
        <li v-for="t in typer" :key="t.id"><span class="ruta" :style="{ background: t.farg }" />{{ t.namn }}</li>
      </ul>
      <p v-if="!s.summa.behandlingar" class="saknas" data-testid="inga">Uppgift saknas för perioden.</p>
      <div v-else class="diagram">
        <svg :viewBox="`0 0 ${B} ${H}`" role="img" :aria-label="`Behandlingar per år och typ ${intervall}`">
          <g class="rutnat">
            <template v-for="t in ticks" :key="t">
              <line :x1="M.left" :x2="B - M.right" :y1="y(t)" :y2="y(t)" />
              <text :x="M.left - 8" :y="y(t) + 4" text-anchor="end">{{ tal(t) }}</text>
            </template>
          </g>
          <text
            v-for="(p, i) in perAr"
            :key="p.ar"
            class="axel"
            :x="M.left + band * i + band / 2"
            :y="H - 8"
            text-anchor="middle"
          >
            {{ p.ar }}
          </text>
          <rect
            v-for="seg in segment"
            :key="`${seg.ar}-${seg.typ.id}`"
            :x="seg.x"
            :y="seg.y"
            :width="stapelB"
            :height="seg.h"
            :rx="seg.topp ? 4 : 0"
            :style="{ fill: seg.typ.farg }"
            data-testid="segment"
            @mouseenter="hover = { ar: seg.ar, namn: seg.typ.namn, n: seg.n, x: seg.x + stapelB / 2, y: seg.y }"
            @mouseleave="hover = null"
          />
        </svg>
        <div
          v-if="hover"
          class="tooltip"
          role="tooltip"
          :style="{ left: `${(hover.x / B) * 100}%`, top: `${(hover.y / H) * 100}%` }"
        >
          <strong>{{ hover.namn }}</strong> {{ hover.ar }}: {{ tal(hover.n) }} behandlingar
          <span class="kalla">Källa: kommunens protokoll</span>
        </div>
      </div>
    </section>

    <section class="kort" aria-labelledby="tabell-rubrik">
      <div class="rubrikrad">
        <h2 id="tabell-rubrik">Per år och organ</h2>
        <a :href="csvLank" :download="`behandlingar-${intervall}.csv`" class="knapp" data-testid="csv">Ladda ned CSV</a>
      </div>
      <div class="rulla">
        <table class="tabell" data-testid="statistiktabell">
          <thead>
            <tr>
              <th scope="col">År</th>
              <th scope="col">Organ</th>
              <th scope="col" class="num">Sammanträden</th>
              <th scope="col" class="num">Behandlingar</th>
              <th v-for="t in typer" :key="t.id" scope="col" class="num">{{ t.namn }}</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="r in s.rader" :key="`${r.ar}-${r.organ.id}`" data-testid="statistikrad" :data-ar="r.ar" :data-organ="r.organ.id">
              <th scope="row">{{ r.ar }}</th>
              <td>{{ r.organ.namn }}</td>
              <td class="num">{{ tal(r.sammantraden) }}</td>
              <td class="num">{{ tal(r.behandlingar) }}</td>
              <td v-for="t in typer" :key="t.id" class="num" :data-typ="t.id">{{ tal(r.antal[t.id]) }}</td>
            </tr>
          </tbody>
          <tfoot v-if="s.rader.length > 1">
            <tr>
              <th scope="row" colspan="2">Summa</th>
              <td class="num">{{ tal(s.summa.sammantraden) }}</td>
              <td class="num">{{ tal(s.summa.behandlingar) }}</td>
              <td v-for="t in typer" :key="t.id" class="num">{{ tal(s.summa.antal[t.id]) }}</td>
            </tr>
          </tfoot>
        </table>
      </div>
      <p class="kallrad">
        Källa: Härnösands kommuns protokoll för {{ intervall }}, automatiskt tolkade, med redaktionens publicerade
        rättelser.
      </p>
    </section>

    <section class="kort" aria-labelledby="underlag-rubrik" data-testid="underlag">
      <h2 id="underlag-rubrik">Underlag</h2>
      <p v-if="ofullstandigt" class="ofullstandigt" data-testid="ofullstandigt">Ofullständigt underlag</p>
      <p>
        {{ tal(s.summa.sammantraden) }} sammanträden med {{ tal(s.summa.behandlingar) }} behandlingar ingår.
      </p>
      <template v-if="s.underlag.ej_tolkade.length">
        <p>
          Protokollen från de här sammanträdena kunde inte tolkas automatiskt, och deras behandlingar saknas i
          siffrorna:
        </p>
        <ul data-testid="ej-tolkade">
          <li v-for="x in s.underlag.ej_tolkade" :key="x.id">
            <RouterLink :to="`/politik/sammantraden/${x.id}`">{{ x.organ.namn }} {{ sammantradesdatum(x.datum) }}</RouterLink>
          </li>
        </ul>
      </template>
      <template v-if="s.underlag.paragrafprotokoll.length">
        <p>De här sammanträdena finns bara som paragrafprotokoll, med en del av behandlingarna:</p>
        <ul>
          <li v-for="x in s.underlag.paragrafprotokoll" :key="x.id">
            <RouterLink :to="`/politik/sammantraden/${x.id}`">{{ x.organ.namn }} {{ sammantradesdatum(x.datum) }}</RouterLink>
          </li>
        </ul>
      </template>
      <p v-if="s.underlag.utan_datum">
        {{ s.underlag.utan_datum }} protokoll saknar datum och kan inte räknas till något år.
      </p>
    </section>
  </template>
</template>

<style scoped>
.vyhuvud {
  margin-bottom: 24px;
}
.ingress {
  color: var(--ink-secondary);
  margin: 0;
  max-width: 70ch;
}
.filter {
  display: flex;
  gap: 16px;
  flex-wrap: wrap;
  margin-bottom: 16px;
}
.filter label {
  display: grid;
  gap: 4px;
  font-size: 13px;
  color: var(--ink-secondary);
}
.filter select {
  font: inherit;
  font-size: 14px;
  color: var(--ink);
  background: var(--surface);
  border: 1px solid var(--line);
  border-radius: var(--radius);
  padding: 6px 8px;
}
.markering {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  font-size: 12px;
  color: var(--ink-secondary);
  border: 1px dotted var(--line-strong);
  border-radius: var(--radius);
  padding: 2px 8px;
  margin: 0 0 16px;
}
.ikon {
  color: var(--ink-muted);
}
.nyckeltal {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(140px, 1fr));
  gap: 12px;
  margin-bottom: 16px;
}
.tal {
  background: var(--surface);
  border: 1px solid var(--line);
  border-radius: var(--radius);
  padding: 12px 16px;
  display: grid;
  gap: 2px;
}
.tal .varde {
  font-size: 24px;
  font-weight: 600;
  color: var(--ink);
  font-variant-numeric: tabular-nums;
}
.tal .etikett {
  font-size: 12px;
  color: var(--ink-secondary);
}
.kort {
  background: var(--surface);
  border: 1px solid var(--line);
  border-radius: var(--radius);
  padding: 16px 24px;
  margin-bottom: 16px;
}
.kort h2 {
  font-size: 15px;
  margin: 0 0 8px;
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
.diagram {
  position: relative;
}
.diagram svg {
  width: 100%;
  height: auto;
  display: block;
}
.rutnat line {
  stroke: var(--line);
  stroke-width: 1;
}
.rutnat text,
.axel {
  font-size: 11px;
  fill: var(--ink-muted);
}
.tooltip {
  position: absolute;
  transform: translate(-50%, calc(-100% - 8px));
  background: var(--surface);
  border: 1px solid var(--line-strong);
  border-radius: var(--radius);
  padding: 6px 10px;
  font-size: 12px;
  color: var(--ink);
  pointer-events: none;
  white-space: nowrap;
}
.tooltip .kalla {
  display: block;
  color: var(--ink-muted);
}
.rubrikrad {
  display: flex;
  justify-content: space-between;
  align-items: baseline;
  gap: 12px;
}
.knapp {
  font-size: 13px;
  color: var(--accent);
}
.rulla {
  overflow-x: auto;
}
.tabell {
  border-collapse: collapse;
  width: 100%;
  font-size: 13px;
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
.tabell tfoot th,
.tabell tfoot td {
  font-weight: 600;
}
.kallrad {
  font-size: 12px;
  color: var(--ink-muted);
  margin: 12px 0 0;
}
.ofullstandigt {
  display: inline-block;
  font-size: 12px;
  color: var(--ink-secondary);
  padding: 2px 8px;
  border-radius: var(--radius);
  background: repeating-linear-gradient(45deg, var(--line) 0 2px, transparent 2px 6px);
}
.saknas {
  color: var(--ink-muted);
  font-style: italic;
}
.fel {
  color: var(--status-critical);
}
a {
  color: var(--accent);
}
</style>
