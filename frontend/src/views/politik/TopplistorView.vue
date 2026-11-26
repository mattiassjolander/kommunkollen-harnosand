<script setup lang="ts">
// Topplistor per år eller mandatperiod (#163). Urvalet speglas i URL:en (design.md, Filter): ?ar=2026, eller
// ?ar=mandatperiod&period=2022. Rubrikerna beskriver vad som räknas och är inte värdeladdade. Listor per parti
// visar alla partier, med antal och antal per mandat, och varje rad har behandlingarna som räknats.
import { computed, inject, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { EjInloggad, hamtaTopplistor, type Partirad, type Topplistor } from '../../api'
import { datum, sammantradesdatum, tal } from '../../format'
import Partimarkering from '../../components/Partimarkering.vue'
import Raknade from '../../components/Raknade.vue'

const route = useRoute()
const router = useRouter()
const utloggad = inject<() => void>('utloggad', () => {})

const t = ref<Topplistor | null>(null)
const laddar = ref(true)
const fel = ref<string | null>(null)

const fraga = (namn: string) => (typeof route.query[namn] === 'string' ? (route.query[namn] as string) : '')

// Urvalet som ett värde i listan: "2026" eller "mandatperiod-2022".
const valt = computed({
  get: () => {
    if (fraga('ar') === 'mandatperiod') return `mandatperiod-${fraga('period') || t.value?.urval.period || ''}`
    return fraga('ar') || (t.value?.urval.ar ? String(t.value.urval.ar) : '')
  },
  set: (v: string) => {
    const [ar, period] = v.startsWith('mandatperiod-') ? ['mandatperiod', v.slice('mandatperiod-'.length)] : [v, undefined]
    router.replace({ query: { ...route.query, ar, period } })
  },
})

async function ladda() {
  laddar.value = true
  fel.value = null
  try {
    t.value = await hamtaTopplistor(fraga('ar') || undefined, fraga('period') || undefined)
  } catch (e) {
    if (e instanceof EjInloggad) return utloggad()
    fel.value = e instanceof Error ? e.message : String(e)
  } finally {
    laddar.value = false
  }
}
onMounted(ladda)
watch(() => [route.query.ar, route.query.period], ladda)

const dagar = (n: number) => `${tal(n)} ${n === 1 ? 'dag' : 'dagar'}`
const kallrad = computed(() =>
  t.value
    ? `Källa: kommunens protokoll, ${tal(t.value.underlag.sammantraden)} sammanträden ${perioden.value}, automatiskt tolkade, med redaktionens publicerade rättelser.`
    : '',
)
const perioden = computed(() => {
  const u = t.value?.urval
  if (!u) return ''
  return u.ar ? `${u.ar}` : `${datum(u.fran)}–${datum(u.till)}`
})
const ofullstandigt = computed(
  () => !!t.value && (t.value.underlag.ej_tolkade.length > 0 || t.value.underlag.paragrafprotokoll.length > 0),
)

// Partilistorna kan ordnas på antal eller antal per mandat.
const partiordning = ref<Record<string, 'antal' | 'per_mandat'>>({})
function partirader(id: string, rader: Partirad[]): Partirad[] {
  if (partiordning.value[id] !== 'per_mandat') return rader
  return [...rader].sort(
    (a, b) =>
      Number(a.parti === null) - Number(b.parti === null) ||
      (b.per_mandat ?? -1) - (a.per_mandat ?? -1) ||
      (a.parti ?? '').localeCompare(b.parti ?? ''),
  )
}
const UTFALL: Record<string, string> = {
  bifall: 'bifall',
  avslag: 'avslag',
  besvarad: 'besvarad',
  delvis: 'delvis bifall',
  annat: 'annat beslut',
}
const perMandat = (v: number | null) => (v === null ? '–' : v.toLocaleString('sv-SE', { minimumFractionDigits: 2, maximumFractionDigits: 2 }))
const procent = (v: number) => `${v.toLocaleString('sv-SE', { minimumFractionDigits: 1, maximumFractionDigits: 1 })} %`
const fler = (totalt: number, visade: number) => (totalt > visade ? `De ${visade} första av ${tal(totalt)}.` : '')
</script>

<template>
  <header class="vyhuvud">
    <h1>Topplistor</h1>
    <p class="ingress">
      Ärenden, partier, ledamöter och voteringar ordnade efter ett mått, för ett år eller en mandatperiod. Varje rad
      visar behandlingarna som räknats. Det finns ingen lista över närvaro per person, eftersom frånvaro kan bero på
      sjukdom eller föräldraledighet.
    </p>
  </header>

  <div class="filter">
    <label>
      Period
      <select v-model="valt" data-testid="topplisteurval">
        <option v-for="a in [...(t?.val.ar ?? [])].reverse()" :key="a" :value="String(a)">{{ a }}</option>
        <option v-for="p in t?.val.perioder ?? []" :key="p.valar" :value="`mandatperiod-${p.valar}`">
          Mandatperioden {{ p.namn }}
        </option>
      </select>
    </label>
  </div>

  <p v-if="fel" class="fel" role="alert">Kunde inte hämta topplistorna: {{ fel }}</p>
  <p v-else-if="laddar && !t" class="saknas">Hämtar topplistorna …</p>
  <template v-else-if="t">
    <p v-if="ofullstandigt" class="ofullstandigt" data-testid="ofullstandigt">
      Ofullständigt underlag, se <a href="#underlag-rubrik">Underlag</a>
    </p>
    <div class="listor" :aria-busy="laddar">
      <!-- Ärenden -->
      <section class="kort" aria-labelledby="langsta-beredning" data-testid="topplista" data-lista="langsta_beredning">
        <h2 id="langsta-beredning">Längsta beredning</h2>
        <p class="regel">
          Avgjorda ärenden med längst tid från första behandlingen till det slutliga beslutet. Ett ärende räknas till
          perioden då det slutliga beslutet fattades.
        </p>
        <p v-if="!t.listor.langsta_beredning.rader.length" class="saknas">Inga avgjorda ärenden med flera behandlingar.</p>
        <div v-else class="rulla">
          <table class="tabell">
            <thead>
              <tr><th scope="col" class="num">Plats</th><th scope="col">Ärende</th><th scope="col" class="num">Beredning</th><th scope="col">Räknade</th></tr>
            </thead>
            <tbody>
              <tr v-for="r in t.listor.langsta_beredning.rader" :key="r.arende_id" data-testid="topplisterad">
                <td class="num">{{ r.plats }}</td>
                <td>
                  <RouterLink :to="`/politik/arenden/${r.arende_id}`">{{ r.rubrik }}</RouterLink>
                  <span class="meta">{{ datum(r.fran) }} till {{ datum(r.till) }}</span>
                </td>
                <td class="num">{{ dagar(r.dagar) }}</td>
                <td><Raknade :behandlingar="r.behandlingar" /></td>
              </tr>
            </tbody>
          </table>
        </div>
        <p class="kallrad">{{ fler(t.listor.langsta_beredning.totalt, t.listor.langsta_beredning.rader.length) }} {{ kallrad }}</p>
      </section>

      <section class="kort" aria-labelledby="langst-pagaende" data-testid="topplista" data-lista="langst_pagaende">
        <h2 id="langst-pagaende">Längst pågående</h2>
        <p class="regel">
          Ärenden utan slutligt beslut, med längst tid från första behandlingen till i dag ({{ datum(t.idag) }}): obesvarade
          motioner och medborgarförslag, återremitterade och bordlagda ärenden och förslag som väntar på beslut i ett
          annat organ. Ett ärende är med när någon av dess behandlingar ligger i perioden.
        </p>
        <p v-if="!t.listor.langst_pagaende.rader.length" class="saknas">Inga pågående ärenden.</p>
        <div v-else class="rulla">
          <table class="tabell">
            <thead>
              <tr><th scope="col" class="num">Plats</th><th scope="col">Ärende</th><th scope="col" class="num">Pågått</th><th scope="col">Räknade</th></tr>
            </thead>
            <tbody>
              <tr v-for="r in t.listor.langst_pagaende.rader" :key="r.arende_id" data-testid="topplisterad">
                <td class="num">{{ r.plats }}</td>
                <td>
                  <RouterLink :to="`/politik/arenden/${r.arende_id}`">{{ r.rubrik }}</RouterLink>
                  <span class="meta">{{ r.status }}, sedan {{ datum(r.fran) }}</span>
                </td>
                <td class="num">{{ dagar(r.dagar) }}</td>
                <td><Raknade :behandlingar="r.behandlingar" /></td>
              </tr>
            </tbody>
          </table>
        </div>
        <p class="kallrad">{{ fler(t.listor.langst_pagaende.totalt, t.listor.langst_pagaende.rader.length) }} {{ kallrad }}</p>
      </section>

      <!-- Partier: alla partier, med antal och antal per mandat -->
      <section
        v-for="lista in [
          {
            id: 'reservationer_per_parti',
            rubrik: 'Reservationer per parti',
            regel: 'Behandlingar under perioden där partiet, som grupp eller genom någon av sina ledamöter, reserverade sig. En behandling räknas en gång per parti.',
            enhet: 'Reservationer',
          },
          {
            id: 'motioner_per_parti',
            rubrik: 'Motioner per parti',
            regel: 'Motioner som väcktes under perioden. En motion från ledamöter i flera partier räknas för vart och ett av partierna.',
            enhet: 'Motioner',
          },
        ] as const"
        :key="lista.id"
        class="kort"
        :aria-labelledby="lista.id"
        data-testid="topplista"
        :data-lista="lista.id"
      >
        <h2 :id="lista.id">{{ lista.rubrik }}</h2>
        <p class="regel">
          {{ lista.regel }}
          <template v-if="t.mandat">
            Per mandat räknas på de {{ t.mandat.totalt }} mandaten i kommunfullmäktige under mandatperioden
            {{ t.mandat.period }}.
          </template>
          <template v-else>Mandatfördelningen saknas för perioden, så antal per mandat kan inte räknas.</template>
        </p>
        <div class="ordna" role="group" :aria-label="`Ordna ${lista.rubrik.toLowerCase()}`">
          <button
            type="button"
            class="lankknapp"
            :aria-pressed="partiordning[lista.id] !== 'per_mandat'"
            @click="partiordning = { ...partiordning, [lista.id]: 'antal' }"
          >
            Antal
          </button>
          <button
            type="button"
            class="lankknapp"
            :aria-pressed="partiordning[lista.id] === 'per_mandat'"
            :disabled="!t.mandat"
            data-testid="ordna-per-mandat"
            @click="partiordning = { ...partiordning, [lista.id]: 'per_mandat' }"
          >
            Per mandat
          </button>
        </div>
        <div class="rulla">
          <table class="tabell">
            <thead>
              <tr>
                <th scope="col">Parti</th>
                <th scope="col" class="num">{{ lista.enhet }}</th>
                <th scope="col" class="num">Mandat</th>
                <th scope="col" class="num">Per mandat</th>
                <th scope="col">Räknade</th>
              </tr>
            </thead>
            <tbody>
              <tr
                v-for="r in partirader(lista.id, t.listor[lista.id].rader)"
                :key="r.parti ?? 'okant'"
                data-testid="partirad"
                :data-parti="r.parti ?? ''"
              >
                <th scope="row"><Partimarkering :parti="r.parti" /></th>
                <td class="num">{{ tal(r.antal) }}</td>
                <td class="num">{{ r.mandat ?? '–' }}</td>
                <td class="num" data-testid="per-mandat">{{ perMandat(r.per_mandat) }}</td>
                <td><Raknade :behandlingar="r.behandlingar" /></td>
              </tr>
            </tbody>
          </table>
        </div>
        <p class="kallrad">
          {{ kallrad }}<template v-if="t.mandat"> Mandaten: Valmyndigheten, valet {{ t.mandat.valar }}.</template>
        </p>
      </section>

      <!-- Ledamöter: bara personer i ledamotsregistret -->
      <section
        v-for="lista in [
          {
            id: 'reservationer_per_ledamot',
            rubrik: 'Reservationer per ledamot',
            regel: 'Behandlingar under perioden där ledamoten reserverade sig med namn. En reservation från en hel partigrupp räknas för partiet men inte för enskilda ledamöter.',
            enhet: 'Reservationer',
          },
          {
            id: 'yrkanden_per_ledamot',
            rubrik: 'Yrkanden per ledamot',
            regel: 'Yrkanden under perioden där ledamoten står med namn. Ett gemensamt yrkande räknas för var och en som står bakom det.',
            enhet: 'Yrkanden',
          },
        ] as const"
        :key="lista.id"
        class="kort"
        :aria-labelledby="lista.id"
        data-testid="topplista"
        :data-lista="lista.id"
      >
        <h2 :id="lista.id">{{ lista.rubrik }}</h2>
        <p class="regel">{{ lista.regel }} Bara personer i ledamotsregistret räknas.</p>
        <p v-if="!t.listor[lista.id].rader.length" class="saknas">Inga under perioden.</p>
        <div v-else class="rulla">
          <table class="tabell">
            <thead>
              <tr><th scope="col" class="num">Plats</th><th scope="col">Ledamot</th><th scope="col" class="num">{{ lista.enhet }}</th><th scope="col">Räknade</th></tr>
            </thead>
            <tbody>
              <tr v-for="r in t.listor[lista.id].rader" :key="r.person_id" data-testid="topplisterad">
                <td class="num">{{ r.plats }}</td>
                <td>
                  <RouterLink :to="`/politik/ledamoter/${r.person_id}`">{{ r.namn }}</RouterLink>
                  <Partimarkering :parti="r.parti" class="parti" />
                </td>
                <td class="num">{{ tal(r.antal) }}</td>
                <td><Raknade :behandlingar="r.behandlingar" /></td>
              </tr>
            </tbody>
          </table>
        </div>
        <p class="kallrad">{{ fler(t.listor[lista.id].totalt, t.listor[lista.id].rader.length) }} {{ kallrad }}</p>
      </section>

      <section class="kort" aria-labelledby="langsta-ledtid" data-testid="topplista" data-lista="langsta_ledtid_motioner">
        <h2 id="langsta-ledtid">Längsta ledtid för motioner</h2>
        <p class="regel">
          Motioner med längst tid från att de väcktes till att kommunfullmäktige besvarade dem. En motion räknas till
          perioden då den besvarades.
        </p>
        <p v-if="!t.listor.langsta_ledtid_motioner.rader.length" class="saknas">Inga motioner besvarades under perioden.</p>
        <div v-else class="rulla">
          <table class="tabell">
            <thead>
              <tr><th scope="col" class="num">Plats</th><th scope="col">Motion</th><th scope="col" class="num">Ledtid</th><th scope="col">Räknade</th></tr>
            </thead>
            <tbody>
              <tr v-for="r in t.listor.langsta_ledtid_motioner.rader" :key="r.arende_id" data-testid="topplisterad">
                <td class="num">{{ r.plats }}</td>
                <td>
                  <RouterLink :to="`/politik/arenden/${r.arende_id}`">{{ r.rubrik }}</RouterLink>
                  <span class="meta">
                    Väckt {{ datum(r.vackt) }}, besvarad {{ datum(r.besvarad) }}<template v-if="r.utfall">, {{ UTFALL[r.utfall] }}</template>
                  </span>
                </td>
                <td class="num">{{ dagar(r.dagar) }}</td>
                <td><Raknade :behandlingar="r.behandlingar" /></td>
              </tr>
            </tbody>
          </table>
        </div>
        <p class="kallrad">{{ fler(t.listor.langsta_ledtid_motioner.totalt, t.listor.langsta_ledtid_motioner.rader.length) }} {{ kallrad }}</p>
      </section>

      <section class="kort" aria-labelledby="jamnaste-voteringar" data-testid="topplista" data-lista="jamnaste_voteringar">
        <h2 id="jamnaste-voteringar">Jämnaste voteringar</h2>
        <p class="regel">
          Voteringar under perioden med minst skillnad mellan ja och nej, i procent av ja- och nejrösterna. Står
          siffrorna inte i protokollets text räknas de ur voteringslistan.
        </p>
        <p v-if="!t.listor.jamnaste_voteringar.rader.length" class="saknas">Inga voteringar under perioden.</p>
        <div v-else class="rulla">
          <table class="tabell">
            <thead>
              <tr><th scope="col" class="num">Plats</th><th scope="col">Behandling</th><th scope="col" class="num">Ja–nej</th><th scope="col" class="num">Skillnad</th></tr>
            </thead>
            <tbody>
              <tr
                v-for="r in t.listor.jamnaste_voteringar.rader"
                :key="`${r.behandling.sammantrade.id}-${r.behandling.paragraf}-${r.votering}`"
                data-testid="topplisterad"
              >
                <td class="num">{{ r.plats }}</td>
                <td>
                  <RouterLink :to="`/politik/sammantraden/${r.behandling.sammantrade.id}/paragraf/${r.behandling.paragraf}`">{{
                    r.behandling.rubrik
                  }}</RouterLink>
                  <span class="meta">
                    {{ r.behandling.sammantrade.organ.namn }} {{ sammantradesdatum(r.behandling.sammantrade.datum) }} §
                    {{ r.behandling.paragraf }}<template v-if="r.antal_voteringar > 1">, votering {{ r.votering }} av {{ r.antal_voteringar }}</template>
                  </span>
                </td>
                <td class="num">{{ r.ja }}–{{ r.nej }}</td>
                <td class="num" data-testid="skillnad">{{ procent(r.skillnad_procent) }}</td>
              </tr>
            </tbody>
          </table>
        </div>
        <p class="kallrad">{{ fler(t.listor.jamnaste_voteringar.totalt, t.listor.jamnaste_voteringar.rader.length) }} {{ kallrad }}</p>
      </section>
    </div>

    <section class="kort" aria-labelledby="underlag-rubrik" data-testid="underlag">
      <h2 id="underlag-rubrik">Underlag</h2>
      <p>
        {{ tal(t.underlag.sammantraden) }} sammanträden {{ perioden }} ingår. Listorna räknas ur de automatiskt tolkade
        protokollen med redaktionens publicerade rättelser.
      </p>
      <template v-if="t.underlag.ej_tolkade.length">
        <p>Protokollen från de här sammanträdena kunde inte tolkas automatiskt, och deras behandlingar saknas i listorna:</p>
        <ul data-testid="ej-tolkade">
          <li v-for="x in t.underlag.ej_tolkade" :key="x.id">
            <RouterLink :to="`/politik/sammantraden/${x.id}`">{{ x.organ.namn }} {{ sammantradesdatum(x.datum) }}</RouterLink>
          </li>
        </ul>
      </template>
      <template v-if="t.underlag.paragrafprotokoll.length">
        <p>De här sammanträdena finns bara som paragrafprotokoll, med en del av behandlingarna:</p>
        <ul>
          <li v-for="x in t.underlag.paragrafprotokoll" :key="x.id">
            <RouterLink :to="`/politik/sammantraden/${x.id}`">{{ x.organ.namn }} {{ sammantradesdatum(x.datum) }}</RouterLink>
          </li>
        </ul>
      </template>
      <p v-if="t.underlag.utan_datum">{{ t.underlag.utan_datum }} protokoll saknar datum och kan inte räknas till någon period.</p>
      <p><RouterLink to="/politik/avvikelser">Se alla avvikelser i protokollen</RouterLink></p>
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
.listor {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(min(100%, 520px), 1fr));
  gap: 16px;
  margin-bottom: 16px;
  align-items: start;
}
.listor[aria-busy='true'] {
  opacity: 0.6;
}
.kort {
  background: var(--surface);
  border: 1px solid var(--line);
  border-radius: var(--radius);
  padding: 16px 24px;
  min-width: 0;
}
.kort[data-testid='underlag'] {
  margin-bottom: 16px;
}
.kort h2 {
  font-size: 15px;
  margin: 0 0 4px;
}
.regel {
  margin: 0 0 12px;
  font-size: 13px;
  color: var(--ink-secondary);
  max-width: 70ch;
}
.rulla {
  overflow-x: auto;
}
.tabell {
  width: 100%;
  border-collapse: collapse;
  font-size: 14px;
}
.tabell th,
.tabell td {
  text-align: left;
  padding: 6px 8px;
  border-bottom: 1px solid var(--line);
  vertical-align: top;
}
.tabell thead th {
  font-size: 12px;
  font-weight: 600;
  color: var(--ink-secondary);
}
.tabell tbody th {
  font-weight: normal;
}
.tabell .num {
  text-align: right;
  font-variant-numeric: tabular-nums;
  white-space: nowrap;
}
.meta {
  display: block;
  font-size: 12px;
  color: var(--ink-secondary);
}
.parti {
  margin-left: 6px;
  font-size: 13px;
}
.ordna {
  display: flex;
  gap: 4px;
  margin-bottom: 8px;
}
.lankknapp {
  font: inherit;
  font-size: 13px;
  color: var(--ink-secondary);
  background: none;
  border: 1px solid var(--line);
  border-radius: var(--radius);
  padding: 2px 8px;
  cursor: pointer;
}
.lankknapp:hover:not(:disabled),
.lankknapp[aria-pressed='true'] {
  background: var(--accent-wash);
  color: var(--accent);
  border-color: var(--accent);
}
.lankknapp:disabled {
  cursor: default;
  opacity: 0.5;
}
.kallrad {
  margin: 8px 0 0;
  font-size: 12px;
  color: var(--ink-muted);
}
.ofullstandigt {
  display: inline-block;
  font-size: 12px;
  color: var(--ink-secondary);
  padding: 2px 8px;
  border-radius: var(--radius);
  background: repeating-linear-gradient(45deg, var(--line) 0 2px, transparent 2px 6px);
  margin: 0 0 16px;
}
.ofullstandigt a {
  color: inherit;
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
