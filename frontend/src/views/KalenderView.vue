<script setup lang="ts">
// Kalendern över sammanträden (#68): kommande sammanträden för de fem organen, i en lista och i en månadsvy.
// Inställda sammanträden är överstrukna. Flödena går att prenumerera på i telefonen, i Google Kalender eller
// med en kopierad länk, och varje sammanträde går att ladda ner som en .ics-fil.
// Organ, vy, månad och valt sammanträde står i URL:en (design.md, Filter).
import { computed, inject, nextTick, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { EjInloggad, hamtaKalender, type Kalender, type Kalenderhandelse } from '../api'
import { sammantradesdatum } from '../format'

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
const vy = fraga('vy') // '' = lista, 'manad' = månadsvy
const valdManad = fraga('manad') // ÅÅÅÅ-MM
const valt = computed(() => (route.query.sammantrade ? Number(route.query.sammantrade) : null))

const k = ref<Kalender | null>(null)
const laddar = ref(true)
const fel = ref<string | null>(null)
const kopierad = ref(false)

onMounted(async () => {
  try {
    k.value = await hamtaKalender()
  } catch (e) {
    if (e instanceof EjInloggad) return utloggad()
    fel.value = e instanceof Error ? e.message : String(e)
  } finally {
    laddar.value = false
  }
  if (valt.value !== null) {
    await nextTick()
    document.getElementById(`sammantrade-${valt.value}`)?.scrollIntoView({ block: 'center' })
  }
})

const handelser = computed(() =>
  (k.value?.handelser ?? []).filter((h) => !valtOrgan.value || h.organ.id === valtOrgan.value),
)
const idag = computed(() => k.value?.idag ?? new Date().toISOString().slice(0, 10))
const kommande = computed(() => handelser.value.filter((h) => h.datum >= idag.value))
const tidigare = computed(() => handelser.value.filter((h) => h.datum < idag.value).reverse())
const valtTidigare = computed(() => tidigare.value.some((h) => h.id === valt.value))

const MANAD = new Intl.DateTimeFormat('sv-SE', { month: 'long', year: 'numeric', timeZone: 'UTC' })
function manadsnamn(manad: string): string {
  const s = MANAD.format(new Date(`${manad}-15T12:00:00Z`))
  return s.charAt(0).toUpperCase() + s.slice(1)
}
function perManad(lista: Kalenderhandelse[]): [string, Kalenderhandelse[]][] {
  const m = new Map<string, Kalenderhandelse[]>()
  for (const h of lista) m.set(h.datum.slice(0, 7), [...(m.get(h.datum.slice(0, 7)) ?? []), h])
  return [...m.entries()]
}

// Flöden och prenumeration
const flode = computed(() => (valtOrgan.value ? k.value?.floden.find((f) => f.organ === valtOrgan.value)?.flode : 'alla'))
const flodesnamn = computed(() =>
  valtOrgan.value ? k.value?.floden.find((f) => f.organ === valtOrgan.value)?.namn : 'alla fem organen',
)
const httpsUrl = computed(() => `${window.location.origin}/kalender/${flode.value}.ics`)
const webcalUrl = computed(() => httpsUrl.value.replace(/^https?:/, 'webcal:'))
const googleUrl = computed(() => `https://calendar.google.com/calendar/r?cid=${encodeURIComponent(webcalUrl.value)}`)
async function kopiera() {
  try {
    await navigator.clipboard.writeText(httpsUrl.value)
    kopierad.value = true
    setTimeout(() => (kopierad.value = false), 3000)
  } catch {
    window.prompt('Kopiera länken:', httpsUrl.value)
  }
}

// Månadsvyn: måndag först, veckor som rader.
const manad = computed(() => valdManad.value || idag.value.slice(0, 7))
function flytta(steg: number) {
  const [a, m] = manad.value.split('-').map(Number)
  const d = new Date(Date.UTC(a, m - 1 + steg, 1))
  valdManad.value = d.toISOString().slice(0, 7)
}
const veckor = computed(() => {
  const [a, m] = manad.value.split('-').map(Number)
  const forsta = new Date(Date.UTC(a, m - 1, 1))
  const dagar = new Date(Date.UTC(a, m, 0)).getUTCDate()
  const fore = (forsta.getUTCDay() + 6) % 7
  const celler: (string | null)[] = Array(fore).fill(null)
  for (let d = 1; d <= dagar; d++) celler.push(`${manad.value}-${String(d).padStart(2, '0')}`)
  while (celler.length % 7) celler.push(null)
  return Array.from({ length: celler.length / 7 }, (_, i) => celler.slice(i * 7, i * 7 + 7))
})
const perDag = computed(() => {
  const m = new Map<string, Kalenderhandelse[]>()
  for (const h of handelser.value) m.set(h.datum, [...(m.get(h.datum) ?? []), h])
  return m
})
const forstaManad = computed(() => handelser.value[0]?.datum.slice(0, 7) ?? manad.value)
const sistaManad = computed(() => handelser.value.at(-1)?.datum.slice(0, 7) ?? manad.value)

function tid(h: Kalenderhandelse): string {
  if (!h.starttid) return 'Tid ej angiven'
  const start = `kl. ${h.starttid.replace(':', '.')}`
  if (!h.sluttid) return start
  return `${start}–${h.sluttid_ungefarlig ? 'ca ' : ''}${h.sluttid.replace(':', '.')}`
}
const STATUS: Record<Kalenderhandelse['status'], string> = {
  planerat: 'Planerat',
  installt: 'Inställt',
  borttaget: 'Borttaget ur planen',
  hallet: 'Hållet',
}
function storlek(byte: number): string {
  return byte >= 1_000_000 ? `${(byte / 1_000_000).toFixed(0)} MB` : `${Math.max(1, Math.round(byte / 1_000))} kB`
}
const installt = (h: Kalenderhandelse) => h.status === 'installt' || h.status === 'borttaget'

watch(valtOrgan, () => (kopierad.value = false))
// Ett sammanträde som väljs i månadsvyn visas i listan.
watch(valt, async (id) => {
  if (id === null) return
  await nextTick()
  document.getElementById(`sammantrade-${id}`)?.scrollIntoView({ block: 'center' })
})
</script>

<template>
  <header class="vyhuvud">
    <h1>Kalender</h1>
    <p class="ingress">
      När kommunfullmäktige, kommunstyrelsen och nämnderna sammanträder, enligt sammanträdesplanerna på harnosand.se.
      Ändringar, som inställda sammanträden och nya tider, kommer med när plattformen hämtar planerna. Efter ett
      sammanträde finns en länk till protokollet.
    </p>
  </header>

  <p v-if="laddar">Hämtar kalendern…</p>
  <p v-else-if="fel" class="fel" role="alert">{{ fel }}</p>
  <template v-else-if="k">
    <div class="verktyg">
      <label class="filter">
        Organ
        <select v-model="valtOrgan" data-testid="organfilter">
          <option value="">Alla organ</option>
          <option v-for="f in k.floden" :key="f.organ" :value="f.organ">{{ f.namn }}</option>
        </select>
      </label>
      <nav class="vyval" aria-label="Visa som">
        <button type="button" :class="{ aktiv: vy !== 'manad' }" :aria-pressed="vy !== 'manad'" @click="vy = ''">
          Lista
        </button>
        <button
          type="button"
          :class="{ aktiv: vy === 'manad' }"
          :aria-pressed="vy === 'manad'"
          data-testid="manadsvy-knapp"
          @click="vy = 'manad'"
        >
          Månad
        </button>
      </nav>
    </div>

    <section class="prenumerera" aria-labelledby="pren-rubrik" data-testid="prenumerera" :data-flode="flode">
      <h2 id="pren-rubrik">Prenumerera på {{ flodesnamn }}</h2>
      <ul class="alternativ">
        <li>
          <a class="knapp primar" :href="webcalUrl" data-testid="webcal">Prenumerera i telefonen</a>
          <span class="instruktion">Öppnar kalendern i iPhone och de flesta Android-telefoner. Bekräfta prenumerationen.</span>
        </li>
        <li>
          <a class="knapp" :href="googleUrl" target="_blank" rel="noopener" data-testid="google">Lägg till i Google Kalender</a>
          <span class="instruktion">Öppnar Google Kalender i webbläsaren, där du lägger till kalendern.</span>
        </li>
        <li>
          <button type="button" class="knapp" data-testid="kopiera" @click="kopiera">Kopiera länk</button>
          <span class="instruktion">
            För Outlook och andra kalendrar: välj att lägga till en kalender från internet och klistra in länken.
            <span v-if="kopierad" role="status" data-testid="kopierad"> Länken är kopierad.</span>
          </span>
        </li>
      </ul>
      <p class="anteckning">
        Kalendern uppdateras automatiskt. Sluttiden är ungefärlig före sammanträdet. Platsen kommer från kallelsen
        när den står där, annars från organets senaste protokoll. Kommunfullmäktige webbsänds.
      </p>
    </section>

    <section v-if="vy === 'manad'" class="manadsvy" aria-labelledby="manad-rubrik" data-testid="manadsvy">
      <div class="manadshuvud">
        <button type="button" class="knapp" :disabled="manad <= forstaManad" aria-label="Föregående månad" @click="flytta(-1)">
          ‹
        </button>
        <h2 id="manad-rubrik" data-testid="manadsrubrik">{{ manadsnamn(manad) }}</h2>
        <button type="button" class="knapp" :disabled="manad >= sistaManad" aria-label="Nästa månad" @click="flytta(1)">
          ›
        </button>
      </div>
      <table class="manad">
        <thead>
          <tr>
            <th v-for="d in ['Mån', 'Tis', 'Ons', 'Tor', 'Fre', 'Lör', 'Sön']" :key="d" scope="col">{{ d }}</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="(vecka, i) in veckor" :key="i">
            <td v-for="(dag, j) in vecka" :key="j" :class="{ tom: !dag, idag: dag === idag }" :data-dag="dag ?? undefined">
              <template v-if="dag">
                <span class="dagnummer">{{ Number(dag.slice(8)) }}</span>
                <a
                  v-for="h in perDag.get(dag) ?? []"
                  :key="h.id"
                  :href="`#sammantrade-${h.id}`"
                  class="manadshandelse"
                  :class="{ installt: installt(h) }"
                  data-testid="manadshandelse"
                  :data-status="h.status"
                  @click.prevent="router.replace({ query: { ...route.query, vy: undefined, sammantrade: h.id } })"
                >
                  {{ h.organ.namn }}{{ h.starttid ? ` ${h.starttid.replace(':', '.')}` : '' }}
                  <span v-if="installt(h)" class="visually-hidden">(inställt)</span>
                </a>
              </template>
            </td>
          </tr>
        </tbody>
      </table>
    </section>

    <template v-else>
      <section aria-labelledby="kommande-rubrik">
        <h2 id="kommande-rubrik">Kommande sammanträden</h2>
        <p v-if="!kommande.length" class="saknas">Inga kommande sammanträden finns i planerna.</p>
        <div v-for="[m, lista] in perManad(kommande)" :key="m" class="manadsgrupp">
          <h3>{{ manadsnamn(m) }}</h3>
          <ul class="lista" data-testid="kommande">
            <li
              v-for="h in lista"
              :id="`sammantrade-${h.id}`"
              :key="h.id"
              class="handelse"
              :class="{ installt: installt(h), vald: h.id === valt }"
              data-testid="kalenderhandelse"
              :data-organ="h.organ.id"
              :data-datum="h.datum"
              :data-status="h.status"
            >
              <div class="nar">
                <span class="datum">{{ sammantradesdatum(h.datum) }}</span>
                <span class="tid">{{ tid(h) }}</span>
              </div>
              <div class="vad">
                <strong>{{ h.organ.namn }}</strong>
                <span v-if="installt(h)" class="statusetikett">{{ STATUS[h.status] }}</span>
                <span v-if="h.plats && !installt(h)" class="plats" data-testid="plats" :data-kalla="h.plats_kalla">
                  {{ h.plats }}<template v-if="h.plats_antagen"> (enligt senaste protokollet)</template>
                  <template v-else-if="h.plats_kalla === 'kallelse'"> (enligt kallelsen)</template>
                </span>
              </div>
              <div class="lankar">
                <RouterLink v-if="h.protokoll" :to="`/politik/sammantraden/${h.id}`">Protokoll</RouterLink>
                <a v-if="h.kallelse" :href="h.kallelse.url" rel="noopener" data-testid="kallelse">
                  {{ h.kallelse.typ === 'kungorelse' ? 'Kungörelse' : 'Kallelse' }}
                </a>
                <a v-for="x in h.handlingar" :key="x.url" :href="x.url" rel="noopener" data-testid="handlingar">
                  Handlingar<template v-if="x.storlek"> ({{ storlek(x.storlek) }})</template>
                </a>
                <a v-if="h.webbsandning" :href="h.webbsandning.url" rel="noopener" data-testid="webbsandning">
                  {{ h.webbsandning.inspelning ? 'Inspelning' : 'Webb-tv' }}
                </a>
                <a
                  v-if="!installt(h)"
                  :href="`/kalender/sammantraden/${h.id}.ics`"
                  :download="`${h.organ.flode}-${h.datum}.ics`"
                  data-testid="ladda-ner-ics"
                >
                  Lägg till i kalendern
                </a>
              </div>
            </li>
          </ul>
        </div>
      </section>

      <details class="tidigare" :open="valtTidigare">
        <summary>Tidigare sammanträden, de senaste 12 månaderna ({{ tidigare.length }})</summary>
        <ul class="lista" data-testid="tidigare">
          <li
            v-for="h in tidigare"
            :id="`sammantrade-${h.id}`"
            :key="h.id"
            class="handelse"
            :class="{ installt: installt(h), vald: h.id === valt }"
            data-testid="kalenderhandelse"
            :data-organ="h.organ.id"
            :data-datum="h.datum"
            :data-status="h.status"
          >
            <div class="nar">
              <span class="datum">{{ sammantradesdatum(h.datum) }}</span>
              <span class="tid">{{ tid(h) }}</span>
            </div>
            <div class="vad">
              <strong>{{ h.organ.namn }}</strong>
              <span v-if="installt(h)" class="statusetikett">{{ STATUS[h.status] }}</span>
              <span v-if="h.plats && !installt(h)" class="plats">{{ h.plats }}</span>
            </div>
            <div class="lankar">
              <RouterLink v-if="h.protokoll" :to="`/politik/sammantraden/${h.id}`">Protokoll</RouterLink>
              <span v-else-if="!installt(h)" class="anteckning">Protokollet finns inte i Kommunkollen än</span>
              <a v-if="h.kallelse" :href="h.kallelse.url" rel="noopener" data-testid="kallelse">
                {{ h.kallelse.typ === 'kungorelse' ? 'Kungörelse' : 'Kallelse' }}
              </a>
              <a
                v-if="h.webbsandning?.inspelning"
                :href="h.webbsandning.url"
                rel="noopener"
                data-testid="webbsandning"
              >
                Inspelning
              </a>
            </div>
          </li>
        </ul>
      </details>
    </template>
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
.verktyg {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 16px;
}
.filter {
  display: inline-flex;
  gap: 8px;
  align-items: center;
  font-size: 13px;
}
.vyval {
  display: flex;
  gap: 4px;
  border-bottom: 1px solid var(--line);
}
.vyval button {
  font: inherit;
  font-size: 13px;
  padding: 6px 12px;
  border: none;
  border-bottom: 2px solid transparent;
  margin-bottom: -1px;
  background: none;
  color: var(--ink-secondary);
  cursor: pointer;
}
.vyval button.aktiv {
  color: var(--ink);
  font-weight: 600;
  border-bottom-color: var(--accent);
}
.prenumerera {
  background: var(--surface);
  border: 1px solid var(--line);
  border-radius: var(--radius);
  padding: 16px;
  margin-bottom: 24px;
}
.prenumerera h2 {
  font-size: 16px;
  margin: 0 0 12px;
}
.alternativ {
  list-style: none;
  margin: 0;
  padding: 0;
  display: grid;
  gap: 10px;
}
.alternativ li {
  display: grid;
  grid-template-columns: 220px 1fr;
  gap: 12px;
  align-items: center;
}
.instruktion {
  font-size: 13px;
  color: var(--ink-secondary);
}
.knapp {
  font: inherit;
  font-size: 13px;
  padding: 6px 14px;
  border-radius: var(--radius);
  border: 1px solid var(--line);
  background: var(--surface);
  color: var(--ink);
  cursor: pointer;
  text-align: center;
  text-decoration: none;
}
.knapp.primar {
  background: var(--accent);
  border-color: var(--accent);
  color: var(--surface);
}
.knapp:disabled {
  opacity: 0.4;
  cursor: default;
}
.anteckning {
  color: var(--ink-muted);
  font-size: 12px;
  margin: 12px 0 0;
}
h2 {
  font-size: 18px;
}
.manadsgrupp h3 {
  font-size: 14px;
  color: var(--ink-secondary);
  margin: 16px 0 6px;
}
.lista {
  list-style: none;
  margin: 0;
  padding: 0;
}
.handelse {
  display: grid;
  grid-template-columns: 240px 1fr auto;
  gap: 12px;
  padding: 10px 8px;
  border-bottom: 1px solid var(--line);
  font-size: 14px;
}
.handelse.vald {
  background: var(--accent-wash);
}
.nar {
  display: flex;
  flex-direction: column;
}
.tid,
.plats {
  color: var(--ink-secondary);
  font-size: 13px;
}
.vad {
  display: flex;
  flex-direction: column;
}
.lankar {
  display: flex;
  flex-direction: column;
  align-items: flex-end;
  gap: 4px;
  font-size: 13px;
}
.handelse.installt .datum,
.handelse.installt .tid,
.handelse.installt strong {
  text-decoration: line-through;
  color: var(--ink-muted);
}
.statusetikett {
  font-size: 12px;
  font-weight: 600;
  color: var(--ink-secondary);
}
.tidigare {
  margin-top: 24px;
}
.tidigare summary {
  cursor: pointer;
  font-size: 14px;
}
.manadshuvud {
  display: flex;
  align-items: center;
  gap: 12px;
}
.manadshuvud h2 {
  min-width: 180px;
  text-align: center;
  margin: 0;
}
.manad {
  width: 100%;
  border-collapse: collapse;
  table-layout: fixed;
  margin-top: 12px;
  font-size: 12px;
}
.manad th {
  color: var(--ink-secondary);
  font-weight: 600;
  padding: 4px;
  text-align: left;
}
.manad td {
  border: 1px solid var(--line);
  height: 84px;
  vertical-align: top;
  padding: 4px;
}
.manad td {
  background: var(--surface);
}
.manad td.tom {
  background: var(--page);
}
.manad td.idag .dagnummer {
  font-weight: 700;
  color: var(--accent);
}
.dagnummer {
  display: block;
  color: var(--ink-secondary);
  margin-bottom: 2px;
}
.manadshandelse {
  display: block;
  margin-bottom: 4px;
  line-height: 1.3;
  overflow-wrap: anywhere;
}
.manadshandelse.installt {
  text-decoration: line-through;
  color: var(--ink-muted);
}
.visually-hidden {
  position: absolute;
  width: 1px;
  height: 1px;
  overflow: hidden;
  clip: rect(0 0 0 0);
}
.saknas {
  color: var(--ink-secondary);
}
.fel {
  color: var(--status-critical);
}
@media (max-width: 640px) {
  .alternativ li,
  .handelse {
    grid-template-columns: 1fr;
  }
  .lankar {
    align-items: flex-start;
  }
}
</style>
