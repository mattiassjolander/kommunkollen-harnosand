<script setup lang="ts">
// Avvikelser i protokollen: en samlad lista att gå igenom och vid behov lämna till kommunen.
// Varje publicerad rättelse listas med före och efter och var felet finns (#74).
// Organ, årsintervall, kategori och var felet finns speglas i URL:en (design.md, Filter).
import { computed, inject, nextTick, onMounted, ref, watch, type Ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import {
  EjInloggad,
  FELET_I,
  hamtaAvvikelser,
  hamtaOrgan,
  type Avvikelser,
  type Avvikelserattelse,
  type Jag,
  type Organ,
} from '../../api'
import { rattelseuppgift, rattelsevarde, sammantradesdatum, tal } from '../../format'
import PolitikFlikar from '../../components/PolitikFlikar.vue'
import Avvikelsetext from '../../components/Avvikelsetext.vue'

const route = useRoute()
const router = useRouter()
const utloggad = inject<() => void>('utloggad', () => {})
const jag = inject<Ref<Jag | null>>('jag', ref(null))
const arRedaktor = computed(() => jag.value?.roller.includes('redaktor') ?? false)

function fraga(namn: string) {
  return computed<string>({
    get: () => (typeof route.query[namn] === 'string' ? (route.query[namn] as string) : ''),
    set: (v) => router.replace({ query: { ...route.query, [namn]: v || undefined } }),
  })
}
const valtOrgan = fraga('organ')
const fran = fraga('fran')
const till = fraga('till')
const kategori = fraga('kategori')
const felet = fraga('felet')

const organ = ref<Organ[]>([])
const ar = ref<number[]>([])
const a = ref<Avvikelser | null>(null)
const laddar = ref(true)
const fel = ref<string | null>(null)
const omvant = computed(() => !!fran.value && !!till.value && Number(fran.value) > Number(till.value))

async function ladda() {
  if (omvant.value) return
  laddar.value = true
  fel.value = null
  try {
    a.value = await hamtaAvvikelser(fran.value, till.value, valtOrgan.value || undefined)
    if (!ar.value.length) ar.value = Array.from({ length: a.value.till - a.value.fran + 1 }, (_, i) => a.value!.fran + i)
    // En länk från markeringen "Innehåller felaktigheter" pekar på protokollet i listan.
    if (route.hash) nextTick(() => document.getElementById(route.hash.slice(1))?.scrollIntoView())
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

const franAr = computed({ get: () => fran.value || String(a.value?.fran ?? ''), set: (v) => (fran.value = v) })
const tillAr = computed({ get: () => till.value || String(a.value?.till ?? ''), set: (v) => (till.value = v) })
const namn = computed(() => Object.fromEntries((a.value?.kategorier ?? []).map((k) => [k.id, k.namn])) as Record<string, string>)
const feletI = (x: Avvikelserattelse) => x.felet_i ?? 'ej_angivet'
const matchar = (x: Avvikelserattelse) => !felet.value || feletI(x) === felet.value
const visade = computed(() =>
  (a.value?.sammantraden ?? []).filter(
    (s) =>
      (!kategori.value ||
        (kategori.value === 'rattelser' ? s.rattelser.length > 0 : s.avvikelser.some((x) => x.kategori === kategori.value))) &&
      (!felet.value || s.rattelser.some(matchar)),
  ),
)
const antalFelet = (id: string) => a.value?.felet_i.find((f) => (f.id ?? 'ej_angivet') === id)?.antal ?? 0
// Vad uppgiften var före rättelsen: protokollets uppgift eller tolkningens.
const fore = (x: Avvikelserattelse) =>
  x.felet_i === 'protokollet' ? 'Protokollet' : x.felet_i === 'inlasningen' ? 'Tolkningen' : 'Före'
function plats(x: Avvikelserattelse): string {
  return x.paragraf === null ? '' : `§ ${x.paragraf}${x.rubrik ? ` ${x.rubrik}` : ''}`
}

function csv(): string {
  const huvud = ['Datum', 'Organ', 'Kategori', 'Avvikelse', 'Protokoll']
  const rader = visade.value.flatMap((s) => [
    ...s.avvikelser.map((x) => [s.sammantrade.datum ?? '', s.sammantrade.organ.namn, namn.value[x.kategori], x.lank ? `${x.text} ${x.lank.url}` : x.text, s.url]),
    ...s.rattelser.filter(matchar).map((x) => [
      s.sammantrade.datum ?? '',
      s.sammantrade.organ.namn,
      `Publicerad rättelse, ${FELET_I[feletI(x)].toLowerCase()}`,
      `${[plats(x), rattelseuppgift(x)].filter(Boolean).join(', ')}: ${rattelsevarde(x.falt, x.ursprungligt)} → ` +
        `${rattelsevarde(x.falt, x.nytt)}. ${x.motivering}`,
      s.url,
    ]),
  ])
  return [huvud, ...rader].map((r) => r.map((v) => `"${String(v).replace(/"/g, '""')}"`).join(';')).join('\n')
}
const csvLank = computed(() => `data:text/csv;charset=utf-8,${encodeURIComponent('﻿' + csv())}`)
</script>

<template>
  <header class="vyhuvud">
    <h1>Politik och beslut</h1>
    <p class="ingress">
      Protokoll där tolkningen hittade något som inte stämmer, eller där redaktionen har publicerat rättelser. En del
      avvikelser finns i själva protokollet och kan lämnas till kommunen. Andra beror på att plattformen inte kunde läsa
      protokollet. Kontrollera alltid mot originalet innan du hör av dig till kommunen.
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
        <option v-for="x in ar" :key="x" :value="String(x)">{{ x }}</option>
      </select>
    </label>
    <label>
      Till år
      <select v-model="tillAr" data-testid="filter-till">
        <option v-for="x in ar" :key="x" :value="String(x)">{{ x }}</option>
      </select>
    </label>
    <label>
      Kategori
      <select v-model="kategori" data-testid="filter-kategori">
        <option value="">Alla</option>
        <option v-for="k in a?.kategorier ?? []" :key="k.id" :value="k.id">{{ k.namn }}</option>
        <option value="rattelser">Publicerade rättelser</option>
      </select>
    </label>
    <label>
      Rättelser, var felet finns
      <select v-model="felet" data-testid="filter-felet">
        <option value="">Alla</option>
        <option v-for="(t, id) in FELET_I" :key="id" :value="id">{{ t }} ({{ tal(antalFelet(id)) }})</option>
      </select>
    </label>
  </div>

  <p v-if="omvant" class="fel" role="alert">Startåret kan inte vara efter slutåret.</p>
  <p v-else-if="fel" class="fel" role="alert">{{ fel }}</p>
  <p v-else-if="laddar && !a">Hämtar avvikelser…</p>
  <template v-else-if="a">
    <section class="nyckeltal" aria-label="Antal avvikelser per kategori">
      <div v-for="k in a.kategorier" :key="k.id" class="tal" :data-kategori="k.id">
        <span class="varde">{{ tal(k.antal) }}</span>
        <span class="etikett">{{ k.namn }}</span>
        <span class="kalla">{{ k.i_protokollet ? 'I protokollet' : 'Kan bero på tolkningen' }}</span>
      </div>
    </section>

    <section class="kort" aria-labelledby="lista-rubrik">
      <div class="rubrikrad">
        <h2 id="lista-rubrik">{{ tal(visade.length) }} av {{ tal(a.granskade) }} protokoll</h2>
        <a :href="csvLank" :download="`avvikelser-${a.fran}-${a.till}.csv`" class="knapp" data-testid="csv">Ladda ned CSV</a>
      </div>
      <p v-if="!visade.length" class="saknas" data-testid="inga">Inga avvikelser för urvalet.</p>
      <ul v-else class="protokoll">
        <li v-for="s in visade" :id="`protokoll-${s.sammantrade.id}`" :key="s.sammantrade.id" data-testid="avvikelse-sammantrade">
          <div class="huvud">
            <RouterLink :to="`/politik/sammantraden/${s.sammantrade.id}`">
              {{ s.sammantrade.organ.namn }} {{ sammantradesdatum(s.sammantrade.datum) }}
            </RouterLink>
            <span v-if="s.i_protokollet" class="etikett-i-protokollet" data-testid="i-protokollet">I protokollet</span>
            <a :href="s.url" class="original" rel="noopener" target="_blank">Originalprotokollet</a>
          </div>
          <ul class="avvikelser">
            <template v-if="!felet">
              <li v-for="(x, i) in s.avvikelser" :key="i" :data-kategori="x.kategori">
                <span class="kategori">{{ namn[x.kategori] }}</span> <Avvikelsetext :avvikelse="x" />
              </li>
            </template>
            <li
              v-for="x in s.rattelser.filter(matchar)"
              :key="`r${x.id}`"
              class="rattelse"
              data-testid="felaktighet"
              :data-felet-i="feletI(x)"
            >
              <span class="kategori">Rättelse, {{ FELET_I[feletI(x)].toLowerCase() }}</span>
              <RouterLink
                v-if="x.paragraf !== null"
                :to="`/politik/sammantraden/${s.sammantrade.id}/paragraf/${x.paragraf}`"
              >{{ plats(x) }}</RouterLink>
              {{ rattelseuppgift(x) }}
              <span class="fore-efter">
                {{ fore(x) }}: <span class="varde">{{ rattelsevarde(x.falt, x.ursprungligt) }}</span>. Rättat:
                <span class="varde" data-testid="rattat">{{ rattelsevarde(x.falt, x.nytt) }}</span>.
              </span>
              <span class="motivering">{{ x.motivering }}</span>
              <RouterLink
                v-if="arRedaktor && !x.felet_i"
                :to="`/politik/rattelser#rattelse-${x.id}`"
                class="komplettera"
                data-testid="komplettera"
              >Ange var felet finns</RouterLink>
            </li>
          </ul>
        </li>
      </ul>
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
.nyckeltal {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(160px, 1fr));
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
  font-variant-numeric: tabular-nums;
}
.tal .etikett {
  font-size: 13px;
  color: var(--ink);
}
.tal .kalla {
  font-size: 12px;
  color: var(--ink-muted);
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
.rubrikrad {
  display: flex;
  justify-content: space-between;
  align-items: baseline;
  gap: 12px;
}
.knapp {
  font-size: 13px;
}
.protokoll {
  list-style: none;
  padding: 0;
  margin: 0;
}
.protokoll > li {
  padding: 12px 0;
  border-bottom: 1px solid var(--line);
}
.huvud {
  display: flex;
  flex-wrap: wrap;
  gap: 8px 12px;
  align-items: baseline;
  font-weight: 600;
}
.original {
  font-size: 12px;
  font-weight: 400;
}
.etikett-i-protokollet {
  font-size: 12px;
  font-weight: 400;
  color: var(--ink-secondary);
  border: 1px solid var(--line-strong);
  border-radius: var(--radius);
  padding: 0 6px;
}
.rattelse .fore-efter,
.rattelse .motivering {
  display: block;
}
.rattelse .motivering {
  color: var(--ink-muted);
  font-size: 12px;
}
.rattelse .varde {
  color: var(--ink);
}
.avvikelser {
  margin: 6px 0 0;
  padding-left: 18px;
  font-size: 13px;
  color: var(--ink-secondary);
}
.kategori {
  color: var(--ink);
  font-weight: 600;
  margin-right: 4px;
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
