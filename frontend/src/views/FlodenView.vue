<script setup lang="ts">
import { computed, inject, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { EjInloggad, hamtaFloden, type Flode, type Flodesmodell } from '../api'
import { procentforandring, siffra, tal, talforandring, visningsskala } from '../format'
import Sankey from '../components/Sankey.vue'
import StatusMarkering from '../components/StatusMarkering.vue'

const route = useRoute()
const router = useRouter()
const modell = ref<Flodesmodell | null>(null)
const laddar = ref(true)
const fel = ref<string | null>(null)
const valt = ref<Flode | null>(null)
const utloggad = inject<() => void>('utloggad', () => {})

// År, jämförelseår och detaljnivå speglas i URL:en: ?ar=2024&jamfor=2023&verksamhet=490
const fraga = (namn: string) => (route.query[namn] as string | undefined) || undefined
const val = computed(() => ({ ar: fraga('ar'), jamfor: fraga('jamfor'), verksamhet: fraga('verksamhet') }))

async function ladda() {
  laddar.value = true
  fel.value = null
  try {
    modell.value = await hamtaFloden(val.value)
    valt.value = null
  } catch (e) {
    if (e instanceof EjInloggad) return utloggad()
    fel.value = e instanceof Error ? e.message : String(e)
  } finally {
    laddar.value = false
  }
}
watch(val, ladda, { immediate: true, deep: true })

function satt(andring: Record<string, string | undefined>) {
  const query = { ...route.query, ...andring }
  for (const k of Object.keys(query)) if (!query[k]) delete query[k]
  router.push({ query })
}

const ar = computed({
  get: () => modell.value?.ar ?? '',
  set: (v: string) => satt({ ar: v }),
})
const jamfor = computed({
  get: () => fraga('jamfor') ?? '',
  set: (v: string) => satt({ jamfor: v || undefined, ar: modell.value?.ar ?? undefined }),
})
const fordjupa = (id: string) => satt({ verksamhet: id.replace('omrade_', ''), ar: modell.value?.ar ?? undefined })
const tillbaka = () => satt({ verksamhet: undefined })

const jamforelseAr = computed(() =>
  [...(modell.value?.tillgangliga_ar ?? [])].reverse().filter((a) => a.ar !== modell.value?.ar),
)
const jamfors = computed(() => !!modell.value?.jamforelse_ar && !!modell.value.jamforelse_fullstandig)
const fordjupbara = computed(() =>
  modell.value?.verksamhet ? [] : (modell.value?.noder ?? []).filter((n) => n.id.startsWith('omrade_')).map((n) => n.id),
)
const mittId = computed(() => modell.value?.noder.find((n) => n.sida === 'mitt')?.id ?? '')

const skala = visningsskala('tkr')
const mnkr = (tkr: number) => tal(tkr * skala.faktor, skala.enhet)
const mnkrForandring = (tkr: number | null) => talforandring(tkr === null ? null : tkr * skala.faktor, skala.enhet)
const forandringMnkr = (tkr: number | null) =>
  tkr === null ? '–' : `${tkr > 0 ? '+' : ''}${siffra(tkr * skala.faktor, 'mnkr')}`
const titel = (id: string) => modell.value?.noder.find((n) => n.id === id)?.titel ?? id
const yttreId = (f: Flode) => (f.till === mittId.value ? f.fran : f.till)
const nod = (f: Flode) => modell.value?.noder.find((n) => n.id === yttreId(f))
const procent = (v: number) => `${siffra(v * 100, '%')} %`
const kronor = (v: number | null) => (v === null ? 'Uppgift saknas' : tal(v, 'kr'))
</script>

<template>
  <header class="vyhuvud">
    <h1>Ekonomiska flöden</h1>
    <p class="ingress">
      Hur kommunens intäkter under ett år används. Bredden på varje flöde motsvarar beloppet. Klicka på ett flöde för
      att se belopp, andel och källa, och på ett verksamhetsområde för att se dess kostnadsslag.
    </p>
  </header>

  <p v-if="laddar && !modell">Hämtar uppgifter…</p>
  <p v-else-if="fel" class="fel">Kunde inte hämta uppgifter: {{ fel }}</p>
  <p v-else-if="modell && !modell.tillgangliga_ar.length" data-testid="tomt">
    Uppgift saknas. Ingen insamling har hämtat räkenskapssammandraget än.
  </p>

  <template v-else-if="modell">
    <nav class="smulor" aria-label="Detaljnivå" data-testid="detaljniva">
      <template v-if="modell.verksamhet">
        <a href="#" data-testid="till-kommunniva" @click.prevent="tillbaka">Kommunnivå</a>
        <span aria-hidden="true"> › </span>
        <span aria-current="page">{{ modell.verksamhet.titel }}</span>
      </template>
      <span v-else aria-current="page">Kommunnivå</span>
    </nav>

    <div class="filterrad">
      <label>
        År
        <select v-model="ar" data-testid="ar">
          <option v-for="a in [...modell.tillgangliga_ar].reverse()" :key="a.ar" :value="a.ar">
            {{ a.ar }}{{ a.fullstandig ? '' : ' (ofullständigt underlag)' }}
          </option>
        </select>
      </label>
      <label>
        Jämför med
        <select v-model="jamfor" data-testid="jamfor">
          <option value="">Inget år</option>
          <option v-for="a in jamforelseAr" :key="a.ar" :value="a.ar">
            {{ a.ar }}{{ a.fullstandig ? '' : ' (ofullständigt underlag)' }}
          </option>
        </select>
      </label>
      <ul class="markeringar" data-testid="flodesinfo">
        <li>{{ modell.flodestyp === 'brutto' ? 'Bruttoflöden' : 'Nettoflöden' }}</li>
        <li>{{ modell.indelning }}</li>
        <li>Löpande priser</li>
      </ul>
    </div>

    <p v-if="modell.jamforelse_ar && !modell.jamforelse_fullstandig" class="notis" data-testid="jamforelse-saknas">
      Jämförelse med {{ modell.jamforelse_ar }} visas inte, eftersom underlaget för det året är ofullständigt.
    </p>
    <p v-else-if="jamfors" class="notis">
      Förändring mot {{ modell.jamforelse_ar }} i löpande priser, alltså utan justering för inflation.
    </p>

    <section v-if="!modell.fullstandig" class="kort ofullstandig" data-testid="ofullstandigt">
      <StatusMarkering status="delvis_fel" :text="`Ofullständigt underlag för ${modell.ar}`" />
      <p>
        Flödena visas inte för det här året, eftersom uppgifter saknas i underlaget. De fylls inte ut med uppskattningar.
      </p>
      <ul>
        <li v-for="s in modell.saknas" :key="s">{{ s }}</li>
      </ul>
    </section>

    <div v-else class="yta">
      <section class="kort diagram">
        <h2 v-if="modell.verksamhet" class="diagramrubrik">{{ modell.verksamhet.titel }}: kostnadsslag</h2>
        <Sankey
          :noder="modell.noder"
          :floden="modell.floden"
          :valt="valt"
          :fordjupbara="fordjupbara"
          @valj="valt = $event"
          @fordjupa="fordjupa"
        />
      </section>

      <aside class="kort detalj" data-testid="flodesdetalj" aria-live="polite">
        <template v-if="valt">
          <h2>{{ titel(valt.fran) }} → {{ titel(valt.till) }}</h2>
          <dl>
            <dt>Belopp</dt>
            <dd class="tal" data-testid="belopp">{{ mnkr(valt.belopp) }}</dd>
            <dt>Andel av totalen</dt>
            <dd class="tal">{{ procent(valt.andel) }}</dd>
            <dt>Per invånare</dt>
            <dd class="tal">{{ kronor(valt.kr_per_invanare) }}</dd>
            <template v-if="valt.jamforelse">
              <dt>{{ modell.jamforelse_ar }}</dt>
              <dd class="tal">
                {{ valt.jamforelse.belopp === null ? 'Fanns inte' : mnkr(valt.jamforelse.belopp) }}
              </dd>
              <dt>Förändring</dt>
              <dd class="tal" data-testid="forandring">{{ mnkrForandring(valt.jamforelse.forandring) }}</dd>
              <dt>Förändring, %</dt>
              <dd class="tal" data-testid="forandring-procent">{{ procentforandring(valt.jamforelse.procent) }}</dd>
            </template>
          </dl>
          <p
            v-if="valt.jamforelse?.titel && valt.jamforelse.titel !== nod(valt)?.titel"
            class="forklaring"
          >
            {{ modell.jamforelse_ar }} var det {{ valt.jamforelse.titel.toLowerCase() }}. Förändringen räknas med tecken.
          </p>
          <p v-if="nod(valt)?.forklaring" class="forklaring">{{ nod(valt)?.forklaring }}</p>
          <button
            v-if="fordjupbara.includes(yttreId(valt))"
            type="button"
            class="knapp"
            data-testid="visa-kostnadsslag"
            @click="fordjupa(yttreId(valt))"
          >
            Visa kostnadsslag för {{ titel(yttreId(valt)) }} ›
          </button>
          <p class="kallrad">
            Källa:
            <template v-for="(k, i) in valt.kallor" :key="k.url">
              <template v-if="i">, </template>
              <a :href="k.url" target="_blank" rel="noopener">{{ k.titel }}</a>
            </template>
            · {{ modell.ar }} · tkr i löpande priser, visas som mnkr
          </p>
        </template>
        <p v-else class="tips">
          Klicka på ett flöde i diagrammet för att se belopp, andel, kronor per invånare och källa.
          <template v-if="fordjupbara.length">Klicka på ett verksamhetsområdes namn för att se dess kostnadsslag.</template>
        </p>
        <p v-if="modell.invanare" class="kallrad">
          Totalt {{ mnkr(modell.totalt ?? 0) }} · {{ tal(modell.invanare) }} invånare 31 december {{ modell.ar }}
          (Kolada N01951)
        </p>
      </aside>
    </div>

    <details v-if="modell.fullstandig" class="kort tabellvy">
      <summary>Visa flödena som tabell</summary>
      <table class="tabell" data-testid="flodestabell">
        <thead>
          <tr>
            <th scope="col">Från</th>
            <th scope="col">Till</th>
            <th scope="col" class="hoger">mnkr {{ modell.ar }}</th>
            <th scope="col" class="hoger">Andel</th>
            <th scope="col" class="hoger">kr/inv</th>
            <template v-if="jamfors">
              <th scope="col" class="hoger">mnkr {{ modell.jamforelse_ar }}</th>
              <th scope="col" class="hoger">Förändring, mnkr</th>
              <th scope="col" class="hoger">Förändring, %</th>
            </template>
          </tr>
        </thead>
        <tbody>
          <tr v-for="f in modell.floden" :key="f.fran + f.till" :class="{ vald: valt === f }" @click="valt = f">
            <td>{{ titel(f.fran) }}</td>
            <td>{{ titel(f.till) }}</td>
            <td class="tal hoger">{{ siffra(f.belopp * skala.faktor, 'mnkr') }}</td>
            <td class="tal hoger">{{ procent(f.andel) }}</td>
            <td class="tal hoger">{{ f.kr_per_invanare === null ? 'Uppgift saknas' : siffra(f.kr_per_invanare, 'kr') }}</td>
            <template v-if="f.jamforelse">
              <td class="tal hoger">
                {{ f.jamforelse.belopp === null ? 'Fanns inte' : siffra(f.jamforelse.belopp * skala.faktor, 'mnkr') }}
              </td>
              <td class="tal hoger">
                {{ forandringMnkr(f.jamforelse.forandring) }}
              </td>
              <td class="tal hoger">{{ procentforandring(f.jamforelse.procent) }}</td>
            </template>
          </tr>
        </tbody>
      </table>
    </details>
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
  margin-bottom: 24px;
  padding-bottom: 16px;
  border-bottom: 1px solid var(--line);
}
.filterrad label {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  color: var(--ink-secondary);
}
.filterrad select {
  font: inherit;
  padding: 4px 8px;
  border: 1px solid var(--line-strong);
  border-radius: var(--radius);
  background: var(--surface-raised);
  color: var(--ink);
}
.markeringar {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin: 0;
  padding: 0;
  list-style: none;
  font-size: 12px;
}
.markeringar li {
  border: 1px solid var(--line-strong);
  border-radius: 999px;
  padding: 2px 10px;
  color: var(--ink-secondary);
}
.kort {
  background: var(--surface);
  border: 1px solid var(--line);
  border-radius: var(--radius);
  padding: 24px;
}
.yta {
  display: grid;
  grid-template-columns: minmax(0, 1fr) 300px;
  gap: 16px;
  align-items: start;
}
@media (max-width: 1100px) {
  .yta {
    grid-template-columns: 1fr;
  }
}
.detalj h2 {
  font-size: 15px;
  margin-bottom: 12px;
}
.detalj dl {
  display: grid;
  grid-template-columns: auto 1fr;
  gap: 4px 16px;
  margin: 0 0 12px;
}
.detalj dt {
  color: var(--ink-secondary);
}
.detalj dd {
  margin: 0;
  text-align: right;
  font-weight: 600;
}
.forklaring,
.tips {
  color: var(--ink-secondary);
  margin: 0 0 12px;
}
.kallrad {
  font-size: 12px;
  color: var(--ink-muted);
  margin: 8px 0 0;
}
.kallrad a {
  color: inherit;
}
.ofullstandig p {
  color: var(--ink-secondary);
}
.tabellvy {
  margin-top: 16px;
}
.tabellvy summary {
  cursor: pointer;
  font-weight: 600;
}
.tabell {
  border-collapse: collapse;
  font-size: 13px;
  width: 100%;
  margin-top: 12px;
}
.tabell th,
.tabell td {
  padding: 4px 16px 4px 0;
  border-bottom: 1px solid var(--line);
  text-align: left;
}
.tabell th {
  color: var(--ink-secondary);
  font-weight: 600;
}
.tabell tbody tr {
  cursor: pointer;
}
.tabell tbody tr:hover,
.tabell tbody tr.vald {
  background: var(--accent-wash);
}
.hoger {
  text-align: right !important;
}
.fel {
  color: var(--status-critical);
}
.smulor {
  font-size: 13px;
  color: var(--ink-secondary);
  margin-bottom: 12px;
}
.smulor a {
  color: var(--accent);
}
.smulor [aria-current] {
  color: var(--ink);
  font-weight: 600;
}
.notis {
  color: var(--ink-secondary);
  font-size: 13px;
  margin: -12px 0 16px;
}
.diagramrubrik {
  font-size: 15px;
  margin-bottom: 8px;
}
.sekundar {
  color: var(--ink-muted);
  font-weight: 400;
}
.knapp {
  font: inherit;
  font-size: 13px;
  padding: 6px 12px;
  margin: 0 0 12px;
  border-radius: var(--radius);
  border: 1px solid var(--line-strong);
  background: var(--surface-raised);
  color: var(--accent);
  cursor: pointer;
}
.knapp:hover {
  background: var(--accent-wash);
}
</style>
