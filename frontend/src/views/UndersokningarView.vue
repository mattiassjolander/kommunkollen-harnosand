<script setup lang="ts">
// Undersökningar (#67): medborgarundersökningen, Insikt och anmälda brott från Kolada, för Härnösand och
// riket. Samma kort och analysverktyg som ekonomisidans nyckeltal (#9, #10). Sidan värderar inte resultaten.
import { computed, inject, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import {
  EjInloggad,
  hamtaUndersokningar,
  hamtaUndersokningsnyckeltal,
  type Nyckeltal,
  type Nyckeltalskort as Kort,
  type Undersokningar,
} from '../api'
import { csv, laddaNer } from '../analys'
import Nyckeltalskort from '../components/Nyckeltalskort.vue'
import Metodbyteskort from '../components/Metodbyteskort.vue'

const route = useRoute()
const router = useRouter()
const data = ref<Undersokningar | null>(null)
const laddar = ref(true)
const fel = ref<string | null>(null)
const utloggad = inject<() => void>('utloggad', () => {})

onMounted(async () => {
  try {
    data.value = await hamtaUndersokningar()
  } catch (e) {
    if (e instanceof EjInloggad) return utloggad()
    fel.value = e instanceof Error ? e.message : String(e)
  } finally {
    laddar.value = false
  }
})

const avsnitt = computed(() => data.value?.avsnitt ?? [])
const allaNyckeltal = computed(() => avsnitt.value.flatMap((a) => a.grupper.flatMap((g) => g.nyckeltal)))
const harData = computed(() => allaNyckeltal.value.some((n) => n.serie?.punkter.length))

// Kortets rubrik utan undersökningens namn, som redan står i avsnittets rubrik.
const kortTitel = (n: Nyckeltal) =>
  n.serie?.matt.titel.replace(/^Medborgarundersökningen - /, '').replace(/^Företagsklimat Insikt - /, '')
const kort = (n: Nyckeltal): Kort => ({ ...n, per_invanare: null, samband: [] })
// "SCB/Kolada" → "SCB". Datakällan (Kolada) står i källraden.
const producent = (kalla: string) => kalla.split('/')[0]

// Alla år där något nyckeltal har ett värde.
const ar = computed(() => {
  const alla = new Set<number>()
  for (const n of allaNyckeltal.value)
    for (const p of n.serie?.punkter ?? []) if (p.varde !== null) alla.add(Number(p.period))
  return [...alla].sort((a, b) => a - b)
})
const forstaAr = computed(() => ar.value[0] ?? new Date().getFullYear())
const senasteAr = computed(() => ar.value[ar.value.length - 1] ?? forstaAr.value)

// Tillståndet ligger i URL:en, som på ekonomisidan: ?fran=2015&till=2024&jamfor=2021-2025&vy=tabell&fraga=N00544
const tal = (namn: string) => Number(route.query[namn]) || null
function satt(andring: Record<string, string | null>) {
  const query: Record<string, string> = {}
  for (const [k, v] of Object.entries({ ...route.query, ...andring })) if (v) query[k] = String(v)
  router.replace({ query, hash: route.hash })
}
const franAr = computed({
  get: () => tal('fran') ?? forstaAr.value,
  set: (v: number) => satt({ fran: v === forstaAr.value ? null : String(v) }),
})
const tillAr = computed({
  get: () => tal('till') ?? senasteAr.value,
  set: (v: number) => satt({ till: v === senasteAr.value ? null : String(v) }),
})
const vy = computed({
  get: () => (route.query.vy === 'tabell' ? 'tabell' : 'diagram') as 'diagram' | 'tabell',
  set: (v: 'diagram' | 'tabell') => satt({ vy: v === 'diagram' ? null : v }),
})
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

// Analysverktyget: alla frågor i medborgarundersökningen, även de som inte är i urvalet. ?fraga=N00544
const fragor = computed(() =>
  (data.value?.medborgarundersokningen ?? []).map((f) => ({
    ...f,
    kort: f.titel.replace(/^Medborgarundersökningen - /, ''),
  })),
)
const fraga = computed({
  get: () => (route.query.fraga as string | undefined) ?? '',
  set: (v: string) => satt({ fraga: v || null }),
})
const valdFraga = ref<Nyckeltal | null>(null)
watch(
  fraga,
  async (id) => {
    valdFraga.value = null
    if (!id) return
    try {
      valdFraga.value = await hamtaUndersokningsnyckeltal(`kolada:${id}`)
    } catch (e) {
      if (e instanceof EjInloggad) return utloggad()
      fel.value = e instanceof Error ? e.message : String(e)
    }
  },
  { immediate: true },
)

function exportera() {
  const alla = [...allaNyckeltal.value, ...(valdFraga.value ? [valdFraga.value] : [])]
  laddaNer(`kommunkollen-undersokningar-${franAr.value}-${tillAr.value}.csv`, csv(alla, franAr.value, tillAr.value, true))
}
</script>

<template>
  <header class="vyhuvud">
    <h1>Undersökningar</h1>
    <p class="ingress">
      Återkommande undersökningar och statistik om Härnösand: SCB:s medborgarundersökning, SKR:s Insikt om
      företagsklimatet och Brås statistik över anmälda brott. Uppgifterna hämtas från Kolada och visas för
      Härnösand och, när Kolada har det, för genomsnittet i riket.
    </p>
  </header>

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
    <p class="notis">
      Det streckade strecket i diagrammen visar genomsnittet för riket enligt Kolada. I tabellen står riket och
      skillnaden mot Härnösand.
    </p>

    <nav class="hopp" aria-label="Avsnitt">
      <a v-for="a in avsnitt" :key="a.id" :href="`#${a.id}`">{{ a.titel }}</a>
    </nav>

    <section v-for="a in avsnitt" :id="a.id" :key="a.id" class="avsnitt" data-testid="avsnitt" :data-avsnitt="a.id">
      <h2>{{ a.titel }}</h2>
      <p class="kalla" data-testid="avsnittskalla">Källa: {{ a.kalla }}</p>
      <p class="gruppingress">{{ a.ingress }}</p>
      <p v-if="a.om_matningen" class="om-matningen" data-testid="om-matningen">{{ a.om_matningen }}</p>

      <div v-for="g in a.grupper" :key="g.titel" class="grupp" data-testid="grupp">
        <!-- Metodbyteskortet har gruppens titel som rubrik. -->
        <h3 v-if="!g.metodbyte" class="grupptitel">{{ g.titel }}</h3>
        <Metodbyteskort
          v-if="g.metodbyte"
          :titel="g.titel"
          :metodbyte="g.metodbyte"
          :nyckeltal="g.nyckeltal"
          :fran-ar="franAr"
          :till-ar="tillAr"
          :vy="vy"
          :producent="producent(a.kalla)"
          @vy="vy = $event"
        />
        <div v-else class="rutnat">
          <Nyckeltalskort
            v-for="n in g.nyckeltal"
            :key="n.id"
            :nyckeltal="kort(n)"
            :titel="kortTitel(n)"
            :producent="producent(a.kalla)"
            :fran-ar="franAr"
            :till-ar="tillAr"
            :vy="vy"
            enhet="totalt"
            :jamforelse="jamforelse"
            :riket="true"
            @vy="vy = $event"
          />
        </div>
      </div>

      <div v-if="a.id === 'medborgarundersokningen' && fragor.length" class="grupp" data-testid="alla-fragor">
        <h3 class="grupptitel">Alla frågor</h3>
        <p class="gruppingress">
          Urvalet ovan är {{ a.grupper.reduce((s, g) => s + g.nyckeltal.length, 0) }} av medborgarundersökningens
          {{ fragor.length }} nyckeltal i Kolada. Välj ett nyckeltal för att se det med samma verktyg.
        </p>
        <label class="valj">
          <span>Nyckeltal</span>
          <select v-model="fraga" data-testid="valj-fraga">
            <option value="">Välj nyckeltal</option>
            <option v-for="f in fragor" :key="f.id" :value="f.id.replace('kolada:', '')">{{ f.kort }}</option>
          </select>
        </label>
        <div v-if="valdFraga" class="rutnat">
          <Nyckeltalskort
            :nyckeltal="kort(valdFraga)"
            :titel="kortTitel(valdFraga)"
            :producent="producent(a.kalla)"
            :fran-ar="franAr"
            :till-ar="tillAr"
            :vy="vy"
            enhet="totalt"
            :jamforelse="jamforelse"
            :riket="true"
            @vy="vy = $event"
          />
        </div>
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
.filterrad select,
.valj select {
  font: inherit;
  padding: 4px 8px;
  border: 1px solid var(--line-strong);
  border-radius: var(--radius);
  background: var(--surface-raised);
  color: var(--ink);
  max-width: 100%;
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
.hopp {
  margin-bottom: 32px;
  display: flex;
  flex-wrap: wrap;
  gap: 4px 16px;
  font-size: 13px;
}
.avsnitt {
  margin-bottom: 56px;
  scroll-margin-top: 16px;
}
.avsnitt h2 {
  margin-bottom: 2px;
}
.kalla {
  font-size: 12px;
  color: var(--ink-muted);
  margin: 0 0 8px;
}
.gruppingress {
  color: var(--ink-secondary);
  margin: 0 0 16px;
  max-width: 70ch;
}
.om-matningen {
  margin: 0 0 24px;
  padding: 8px 12px;
  border-left: 3px solid var(--line-strong);
  background: var(--surface);
  font-size: 13px;
  color: var(--ink-secondary);
  max-width: 80ch;
}
.grupp {
  margin-bottom: 32px;
}
.grupptitel {
  font-size: 15px;
  margin: 0 0 12px;
}
.rutnat {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(min(100%, 520px), 1fr));
  gap: 16px;
}
.valj {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 8px;
  margin-bottom: 16px;
  color: var(--ink-secondary);
  font-size: 13px;
}
.fel {
  color: var(--status-critical);
}
</style>
