<script setup lang="ts">
import { computed, inject, nextTick, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { EjInloggad, hamtaEkonomi, kortankare, varianter, type Huvudtal, type Nyckeltalsgrupp } from '../api'
import { STOR_FORANDRING, csv, laddaNer } from '../analys'
import Nyckeltalskort, { type Enhet } from '../components/Nyckeltalskort.vue'
import Statkort from '../components/Statkort.vue'
import EkonomiFlikar from '../components/EkonomiFlikar.vue'

const STANDARD_FRAN = 2022 // standardvisning enligt kravspec avsnitt 18

const route = useRoute()
const router = useRouter()
const grupper = ref<Nyckeltalsgrupp[]>([])
const huvudtal = ref<Huvudtal[]>([])
const laddar = ref(true)
const fel = ref<string | null>(null)
const utloggad = inject<() => void>('utloggad', () => {})

onMounted(async () => {
  try {
    const svar = await hamtaEkonomi()
    grupper.value = svar.grupper
    huvudtal.value = svar.huvudtal
  } catch (e) {
    if (e instanceof EjInloggad) return utloggad()
    fel.value = e instanceof Error ? e.message : String(e)
  } finally {
    laddar.value = false
  }
  hoppa()
})

// Länkar som /ekonomi#resultat (t.ex. från översikten) hoppar till gruppen, och /ekonomi#kort-… (från ett
// huvudtal) till kortet, som markeras.
async function hoppa() {
  if (!route.hash) return
  await nextTick()
  const mal = document.getElementById(route.hash.slice(1))
  mal?.scrollIntoView()
  if (mal?.classList.contains('kort')) mal.focus({ preventScroll: true })
}
watch(() => route.hash, hoppa)
const markeratKort = computed(() => (route.hash.startsWith('#kort-') ? route.hash.slice(1) : null))

// Alla år som någon serie har.
const ar = computed(() => {
  const alla = new Set<number>()
  for (const g of grupper.value)
    for (const n of g.nyckeltal.flatMap(varianter)) for (const p of n.serie?.punkter ?? []) alla.add(Number(p.period))
  return [...alla].sort((a, b) => a - b)
})
const senasteAr = computed(() => ar.value[ar.value.length - 1] ?? STANDARD_FRAN)

// Hela tillståndet ligger i URL:en, så att en länk visar exakt samma sak:
// ?fran=2015&till=2024&jamfor=2018-2024&vy=tabell&enhet=inv. Standardvärden skrivs inte ut.
const tal = (namn: string) => Number(route.query[namn]) || null
function satt(andring: Record<string, string | null>) {
  const query: Record<string, string> = {}
  for (const [k, v] of Object.entries({ ...route.query, ...andring })) if (v) query[k] = String(v)
  router.replace({ query, hash: route.hash })
}

const franAr = computed({
  get: () => tal('fran') ?? STANDARD_FRAN,
  set: (v: number) => satt({ fran: v === STANDARD_FRAN ? null : String(v), till: v > tillAr.value ? null : route.query.till as string }),
})
const tillAr = computed({
  get: () => tal('till') ?? senasteAr.value,
  set: (v: number) => satt({ till: v === senasteAr.value ? null : String(v) }),
})
const vy = computed({
  get: () => (route.query.vy === 'tabell' ? 'tabell' : 'diagram') as 'diagram' | 'tabell',
  set: (v: 'diagram' | 'tabell') => satt({ vy: v === 'diagram' ? null : v }),
})

// Totalt (mnkr) eller per invånare på de kort som har båda. Gäller alla kort (ADR-0007).
const enhet = computed({
  get: () => (route.query.enhet === 'inv' ? 'inv' : 'totalt') as Enhet,
  set: (v: Enhet) => satt({ enhet: v === 'totalt' ? null : v }),
})

// Huvudtalen: serien hämtas ur kortet, och länken visar kortet i huvudtalets variant.
const oversikt = computed(() =>
  huvudtal.value.flatMap((h) => {
    const kort = grupper.value.flatMap((g) => g.nyckeltal).find((k) => k.id === h.kort)
    const nyckeltal = kort && varianter(kort).find((v) => v.id === h.id)
    if (!kort || !nyckeltal) return []
    const perInvanare = nyckeltal !== kort
    const lank = {
      query: { ...route.query, enhet: perInvanare ? 'inv' : route.query.enhet },
      hash: `#${kortankare(kort.id)}`,
    }
    return [{ ...h, nyckeltal, lank }]
  }),
)

// Jämförelse mellan två år: ?jamfor=2018-2024
const jamforelse = computed<[number, number] | null>(() => {
  const m = /^(\d{4})-(\d{4})$/.exec((route.query.jamfor as string) ?? '')
  return m ? [Number(m[1]), Number(m[2])] : null
})
const jamforFran = computed({
  get: () => jamforelse.value?.[0] ?? '',
  set: (v: number | '') => satt({ jamfor: v === '' ? null : `${v}-${jamforelse.value?.[1] ?? senasteAr.value}` }),
})
const jamforTill = computed({
  get: () => jamforelse.value?.[1] ?? '',
  set: (v: number | '') => satt({ jamfor: v === '' ? null : `${jamforelse.value?.[0] ?? franAr.value}-${v}` }),
})

const harData = computed(() => grupper.value.some((g) => g.nyckeltal.flatMap(varianter).some((n) => n.serie)))
const procentTroskel = `${STOR_FORANDRING.andel * 100} %`

function exportera() {
  const alla = grupper.value.flatMap((g) => g.nyckeltal.flatMap(varianter))
  laddaNer(`kommunkollen-ekonomi-${franAr.value}-${tillAr.value}.csv`, csv(alla, franAr.value, tillAr.value))
}
</script>

<template>
  <header class="vyhuvud">
    <h1>Ekonomi</h1>
    <p class="ingress">
      Härnösands kommuns ekonomiska utveckling över tid. Belopp i löpande priser, alltså inte justerade för
      inflation. Kronor per invånare gör åren lättare att jämföra.
    </p>
  </header>
  <EkonomiFlikar />

  <p v-if="laddar">Hämtar uppgifter…</p>
  <p v-else-if="fel" class="fel">Kunde inte hämta uppgifter: {{ fel }}</p>
  <p v-else-if="!harData" data-testid="tomt">Uppgift saknas. Ingen insamling har körts än.</p>

  <template v-else>
    <div class="filterrad" role="group" aria-label="Filter">
      <fieldset>
        <legend>Period</legend>
        <select v-model.number="franAr" data-testid="fran-ar" aria-label="Från år">
          <option v-for="a in ar" :key="a" :value="a" :disabled="a > tillAr">{{ a }}</option>
        </select>
        <span aria-hidden="true">–</span>
        <select v-model.number="tillAr" data-testid="till-ar" aria-label="Till år">
          <option v-for="a in ar" :key="a" :value="a" :disabled="a < franAr">{{ a }}</option>
        </select>
      </fieldset>
      <fieldset>
        <legend>Jämför</legend>
        <select v-model.number="jamforFran" data-testid="jamfor-fran" aria-label="Jämför från år">
          <option value="">Inget år</option>
          <option v-for="a in ar" :key="a" :value="a">{{ a }}</option>
        </select>
        <span aria-hidden="true">med</span>
        <select v-model.number="jamforTill" data-testid="jamfor-till" aria-label="Jämför med år">
          <option value="">Inget år</option>
          <option v-for="a in ar" :key="a" :value="a">{{ a }}</option>
        </select>
      </fieldset>
      <fieldset>
        <legend>Visa som</legend>
        <div class="vaxel" role="group" aria-label="Visa nyckeltalen som" data-testid="vy">
          <button type="button" :aria-pressed="vy === 'diagram'" @click="vy = 'diagram'">Diagram</button>
          <button type="button" :aria-pressed="vy === 'tabell'" @click="vy = 'tabell'">Tabell</button>
        </div>
      </fieldset>
      <button type="button" class="knapp" data-testid="exportera-alla" @click="exportera">
        Ladda ner alla som CSV
      </button>
    </div>
    <p v-if="jamforelse" class="notis" data-testid="jamforelse-info">
      Förändring {{ jamforelse[0] }}–{{ jamforelse[1] }}. Förändringar på minst {{ procentTroskel }}, eller minst
      {{ STOR_FORANDRING.procentenheter }} procentenheter för nyckeltal i procent, markeras som större.
    </p>
    <section class="oversikt" aria-labelledby="oversikt-rubrik" data-testid="huvudtal">
      <h2 id="oversikt-rubrik">Översikt</h2>
      <p class="gruppingress">
        Fem huvudtal som sammanfattar kommunens ekonomi, med senaste året och förändringen mot året före. Korten
        längre ned visar fler nyckeltal och hela tidsserien.
      </p>
      <div class="huvudtal">
        <Statkort
          v-for="h in oversikt"
          :key="h.id"
          :nyckeltal="h.nyckeltal"
          :lank="h.lank"
          :forklaring="h.forklaring"
        />
      </div>
    </section>

    <nav class="hopp" aria-label="Avsnitt">
      <a v-for="g in grupper" :key="g.id" :href="`#${g.id}`">{{ g.titel }}</a>
    </nav>

    <section v-for="g in grupper" :id="g.id" :key="g.id" class="grupp">
      <h2>{{ g.titel }}</h2>
      <p class="gruppingress">{{ g.ingress }}</p>
      <div class="rutnat">
        <Nyckeltalskort
          v-for="n in g.nyckeltal"
          :key="n.id"
          :class="{ markerad: kortankare(n.id) === markeratKort }"
          :nyckeltal="n"
          :fran-ar="franAr"
          :till-ar="tillAr"
          :vy="vy"
          :enhet="enhet"
          :jamforelse="jamforelse"
          @vy="vy = $event"
          @enhet="enhet = $event"
        />
      </div>
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
.filterrad {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 12px 24px;
  margin-bottom: 32px;
  padding-bottom: 16px;
  border-bottom: 1px solid var(--line);
}
.filterrad fieldset {
  display: inline-flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 8px;
  border: 0;
  padding: 0;
  margin: 0;
  color: var(--ink-secondary);
}
.filterrad legend {
  float: left;
  padding: 0;
  margin-right: 4px;
}
.vaxel {
  display: inline-flex;
  border: 1px solid var(--line-strong);
  border-radius: var(--radius);
  overflow: hidden;
}
.vaxel button {
  font: inherit;
  font-size: 13px;
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
.knapp {
  font: inherit;
  font-size: 13px;
  padding: 4px 12px;
  border-radius: var(--radius);
  border: 1px solid var(--line-strong);
  background: var(--surface-raised);
  color: var(--ink);
  cursor: pointer;
}
.knapp:hover {
  background: var(--accent-wash);
}
.notis {
  color: var(--ink-secondary);
  font-size: 13px;
  margin: -16px 0 16px;
  max-width: 90ch;
}
.filterrad select {
  font: inherit;
  padding: 4px 8px;
  border: 1px solid var(--line-strong);
  border-radius: var(--radius);
  background: var(--surface-raised);
  color: var(--ink);
}
.hopp {
  margin-bottom: 32px;
  display: flex;
  flex-wrap: wrap;
  gap: 4px 16px;
  font-size: 13px;
}
.grupp {
  margin-bottom: 48px;
  scroll-margin-top: 16px;
}
.grupp h2,
.oversikt h2 {
  margin-bottom: 4px;
}
.gruppingress {
  color: var(--ink-secondary);
  margin: 0 0 16px;
  max-width: 70ch;
}
.oversikt {
  margin-bottom: 40px;
}
.huvudtal {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(min(100%, 220px), 1fr));
  gap: 16px;
}
.rutnat {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(min(100%, 520px), 1fr));
  gap: 16px;
}
.fel {
  color: var(--status-critical);
}
</style>
