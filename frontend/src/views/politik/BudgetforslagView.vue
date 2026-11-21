<script setup lang="ts">
// Partiernas budgetförslag (#48) mot gemensamma planförutsättningar (#58): förslagen för ett budgetår
// bredvid varandra, med ram och förändring per nämnd, skattesats, resultat och beräknat resultat.
// Budgetåret speglas i URL:en (design.md, Filter). Varje siffra länkar till sidan i originalet.
// Partier står i alfabetisk ordning (design.md). En nämnd kan öppnas och visar då förslagens åtgärder
// och satsningar för ramen, med belopp, sidlänk och hur stor del av förändringen de förklarar (#57).
import { computed, inject, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import {
  EjInloggad,
  hamtaBudget,
  hamtaBudgetar,
  type Budgetforslag,
  type Budgetjamforelse,
  type Differens,
  type Kalla,
  type Plantabell,
} from '../../api'
import { tal, talforandring } from '../../format'
import Partimarkering from '../../components/Partimarkering.vue'
import PolitikFlikar from '../../components/PolitikFlikar.vue'

const route = useRoute()
const router = useRouter()
const utloggad = inject<() => void>('utloggad', () => {})

const ar = ref<{ budgetar: number; forslag: number; antagen: boolean }[]>([])
const j = ref<Budgetjamforelse | null>(null)
const laddar = ref(true)
const fel = ref<string | null>(null)

const valtAr = computed<number | null>({
  get: () => (typeof route.query.ar === 'string' ? Number(route.query.ar) : (ar.value[0]?.budgetar ?? null)),
  set: (v) => router.replace({ query: { ...route.query, ar: v ? String(v) : undefined } }),
})

async function ladda() {
  if (!valtAr.value) return
  laddar.value = true
  fel.value = null
  try {
    j.value = await hamtaBudget(valtAr.value)
  } catch (e) {
    if (e instanceof EjInloggad) return utloggad()
    fel.value = e instanceof Error ? e.message : String(e)
  } finally {
    laddar.value = false
  }
}
onMounted(async () => {
  try {
    ar.value = await hamtaBudgetar()
  } catch (e) {
    if (e instanceof EjInloggad) return utloggad()
    fel.value = e instanceof Error ? e.message : String(e)
  }
  if (!ar.value.length) laddar.value = false
  await ladda()
})
watch(valtAr, ladda)

const forslag = computed(() => j.value?.forslag ?? [])
const plan = computed(() => j.value?.planforutsattningar ?? null)
const antagen = computed(() => forslag.value.find((f) => f.id === j.value?.antagen) ?? null)
// Länk till sidan i originalet. Ett Word-dokument har inga fasta sidor, så där blir siffran ingen länk.
const lank = (f: Budgetforslag, s?: number) =>
  s ? { href: `${f.original}#page=${s}`, target: '_blank', rel: 'noopener', title: `Sidan ${s}` } : {}
const kallank = (k: Kalla) => `/api/budgetforslag/${k.forslag}/original#page=${k.sida}`

const planram = (o: string) => plan.value?.tabeller.namnder.find((p) => p.post === o) ?? null
const ram = (f: Budgetforslag, o: string) => f.uppgifter.ramar.find((r) => r.organ === o) ?? null
const berakning = (f: Budgetforslag, o: string) => f.berakning?.ramar.find((r) => r.organ === o) ?? null
const diffRam = (f: Budgetforslag, o: string): Differens | null => f.differens?.ramar.find((d) => d.organ === o) ?? null

// Öppnade nämnder, som visar åtgärderna per förslag.
const oppna = ref(new Set<string>())
function vaxla(o: string) {
  const ny = new Set(oppna.value)
  if (ny.has(o)) ny.delete(o)
  else ny.add(o)
  oppna.value = ny
}
const harAtgarder = (o: string) =>
  forslag.value.some((f) => ram(f, o)?.atgarder?.length || berakning(f, o)?.atgarder.saknas)
// "åtgärder för −3,0 av −3,0 mnkr", eller att förslaget ändrar ramen utan att ange några.
function tackningstext(f: Budgetforslag, o: string): string | null {
  const b = berakning(f, o)
  if (!b) return null
  const t = b.atgarder
  if (t.saknas) return 'Inga åtgärder anges'
  if (!t.antal) return null
  if (t.mnkr === null) return t.antal === 1 ? '1 åtgärd utan belopp' : `${t.antal} åtgärder utan belopp`
  return b.forandring !== null
    ? `åtgärder för ${talforandring(t.mnkr, 'mnkr').replace(/ mnkr$/, '')} av ${talforandring(b.forandring, 'mnkr')}`
    : `åtgärder för ${talforandring(t.mnkr, 'mnkr')}`
}
const difftext = (d: Differens) =>
  d.procent === null ? talforandring(d.mnkr, 'mnkr') : `${talforandring(d.mnkr, 'mnkr')} (${talforandring(d.procent, '%')})`

const tvadecimaler = new Intl.NumberFormat('sv-SE', { minimumFractionDigits: 2, maximumFractionDigits: 2 })
const skattesats = (v: number) => `${tvadecimaler.format(v)} %`
const ore = (v: number) => (v === 0 ? 'oförändrad' : `${v > 0 ? '+' : '−'}${Math.abs(v)} öre`)

const planresultat = computed(() => plan.value?.tabeller.resultatbudget.find((p) => p.post === 'Årets resultat')?.mnkr ?? null)

const TABELLER: { nyckel: Plantabell; rubrik: string }[] = [
  { nyckel: 'resultatbudget', rubrik: 'Resultatbudget' },
  { nyckel: 'investeringar', rubrik: 'Investeringsbudget per nämnd' },
  { nyckel: 'balansbudget', rubrik: 'Balansbudget' },
  { nyckel: 'kassaflode', rubrik: 'Förenklad kassaflödesanalys' },
]
</script>

<template>
  <header class="vyhuvud">
    <h1>Politik och beslut</h1>
    <p class="ingress">
      Partiernas budgetförslag till kommunfullmäktige för budgetåret. Alla förslag utgår från samma planförutsättningar:
      förslaget anger sin ram per nämnd, en ändrad skattesats och sitt budgeterade resultat, och förändringen och det
      beräknade resultatet räknas fram. Siffrorna är de som står i förslagen, med länk till sidan i originalet.
    </p>
  </header>
  <PolitikFlikar />

  <p v-if="fel" class="fel" role="alert">{{ fel }}</p>
  <p v-else-if="!laddar && !ar.length" class="saknas" data-testid="inga-budgetar">Inga budgetförslag är publicerade än.</p>
  <template v-else>
    <div class="filter" role="group" aria-label="Filter">
      <label>
        Budgetår
        <select v-model.number="valtAr" data-testid="filter-budgetar">
          <option v-for="a in ar" :key="a.budgetar" :value="a.budgetar">{{ a.budgetar }}</option>
        </select>
      </label>
    </div>

    <p v-if="laddar && !j">Hämtar budgetförslag…</p>
    <template v-else-if="j">
      <section class="kort" aria-labelledby="jamforelse-rubrik">
        <h2 id="jamforelse-rubrik">Budgetförslag {{ j.budgetar }}</h2>
        <p v-if="plan" class="forklaring">
          Under varje ram står förändringen mot planförutsättningarna. Det beräknade resultatet är planförutsättningarnas
          resultat minus förslagets förändringar av ramarna, justerat för en ändrad skattesats. Skiljer det sig från
          förslagets eget resultat saknar förslaget finansiering för skillnaden, eller redovisar den inte.
          <template v-if="antagen">Skillnaden mot den antagna budgeten står sist i varje ruta.</template>
        </p>
        <p v-else class="forklaring" data-testid="utan-planforutsattningar">
          Planförutsättningarna för {{ j.budgetar }} finns inte här, så förslagens ramar visas utan förändring och utan
          beräknat resultat.
        </p>

        <div class="rulla">
          <table class="tabell" data-testid="budgetjamforelse">
            <thead>
              <tr>
                <th scope="col">Mnkr</th>
                <th v-if="plan" scope="col" class="forslag plan" data-testid="plankolumn">
                  <span class="titel">Planförutsättningar</span>
                </th>
                <th v-for="f in j.forslag" :key="f.id" scope="col" class="forslag" :data-nyckel="f.nyckel">
                  <span class="partier">
                    <Partimarkering v-for="p in f.partier" :key="p" :parti="p" />
                  </span>
                  <span class="titel">{{ f.titel }}</span>
                  <span v-if="f.antagen" class="antagen" data-testid="antagen">Antagen budget</span>
                  <span v-if="f.typ === 'tillagg'" class="antagen">Tilläggsbudget</span>
                  <a :href="f.original" class="original" rel="noopener" target="_blank">Originalet</a>
                </th>
              </tr>
            </thead>
            <tbody>
              <template v-for="o in j.organ" :key="o">
              <tr :data-organ="o">
                <th scope="row">
                  <button
                    v-if="harAtgarder(o)"
                    type="button"
                    class="vaxla"
                    :aria-expanded="oppna.has(o)"
                    :aria-controls="`atgarder-${o}`"
                    data-testid="visa-atgarder"
                    @click="vaxla(o)"
                  >
                    <span aria-hidden="true">{{ oppna.has(o) ? '▾' : '▸' }}</span> {{ o }}
                  </button>
                  <template v-else>{{ o }}</template>
                </th>
                <td v-if="plan" class="num plan">{{ planram(o) ? tal(planram(o)!.mnkr, 'mnkr') : '–' }}</td>
                <td v-for="f in j.forslag" :key="f.id" class="num">
                  <template v-if="ram(f, o)">
                    <component :is="ram(f, o)!.sida ? 'a' : 'span'" v-bind="lank(f, ram(f, o)!.sida)">{{ tal(ram(f, o)!.mnkr, 'mnkr') }}</component>
                    <span v-if="berakning(f, o)?.forandring != null" class="diff" data-testid="forandring">{{ talforandring(berakning(f, o)!.forandring, 'mnkr') }}</span>
                    <span v-if="diffRam(f, o)" class="diff" data-testid="differens">mot antagen {{ difftext(diffRam(f, o)!) }}</span>
                  </template>
                  <span v-else class="saknas">{{ plan ? 'Oförändrad' : 'Anges inte' }}</span>
                </td>
              </tr>
              <tr v-if="oppna.has(o)" :id="`atgarder-${o}`" class="atgarder" :data-atgarder="o">
                <th scope="row" class="atgardsrubrik">Åtgärder</th>
                <td v-if="plan" class="plan" />
                <td v-for="f in j.forslag" :key="f.id" data-testid="atgarder">
                  <ul v-if="ram(f, o)?.atgarder?.length" class="atgardslista">
                    <li v-for="(a, i) in ram(f, o)!.atgarder" :key="i">
                      <span class="atgardstext">{{ a.text }}</span>
                      <span v-if="a.mnkr !== undefined" class="atgardsbelopp">{{ talforandring(a.mnkr, 'mnkr') }}</span>
                      <a v-if="a.sida" v-bind="lank(f, a.sida)" class="sidlank">s. {{ a.sida }}</a>
                    </li>
                  </ul>
                  <span
                    v-if="tackningstext(f, o)"
                    :class="berakning(f, o)?.atgarder.saknas ? 'saknas' : 'diff'"
                    data-testid="tackning"
                  >{{ tackningstext(f, o) }}</span>
                </td>
              </tr>
              </template>
              <tr v-if="plan" data-rad="forandring" class="summa">
                <th scope="row">Förändring av ramarna</th>
                <td class="num plan" />
                <td v-for="f in j.forslag" :key="f.id" class="num">{{ talforandring(f.berakning?.forandring ?? null, 'mnkr') }}</td>
              </tr>
              <tr data-rad="skattesats">
                <th scope="row">Skattesats</th>
                <td v-if="plan" class="num plan">{{ skattesats(plan.skattesats.procent) }}</td>
                <td v-for="f in j.forslag" :key="f.id" class="num">
                  <template v-if="f.berakning?.skattesats.procent != null">
                    <component :is="f.uppgifter.skattesats.sida ? 'a' : 'span'" v-bind="lank(f, f.uppgifter.skattesats.sida)">{{ skattesats(f.berakning.skattesats.procent) }}</component>
                    <span v-if="f.berakning.skattesats.ore !== null" class="diff">{{ ore(f.berakning.skattesats.ore) }}</span>
                    <span v-if="f.berakning.skattejustering" class="diff">skatteintäkter {{ talforandring(f.berakning.skattejustering, 'mnkr') }}</span>
                  </template>
                  <span v-else-if="f.berakning?.skattesats.ore" class="diff">{{ ore(f.berakning.skattesats.ore) }}</span>
                  <span v-else class="saknas">Anges inte</span>
                </td>
              </tr>
              <tr data-rad="resultat">
                <th scope="row">Budgeterat resultat</th>
                <td v-if="plan" class="num plan">{{ tal(planresultat, 'mnkr') }}</td>
                <td v-for="f in j.forslag" :key="f.id" class="num">
                  <template v-if="f.berakning?.resultat">
                    <component :is="f.uppgifter.resultat?.sida ? 'a' : 'span'" v-bind="lank(f, f.uppgifter.resultat?.sida)">
                      <template v-if="f.berakning.resultat.mnkr !== null">{{ tal(f.berakning.resultat.mnkr, 'mnkr') }}</template>
                      <template v-else>{{ tal(f.berakning.resultat.procent, '%') }}</template>
                    </component>
                    <span v-if="f.berakning.resultat.mnkr !== null" class="diff">{{ tal(f.berakning.resultat.procent, '%') }} av skatter och bidrag</span>
                  </template>
                  <span v-else class="saknas">Anges inte</span>
                </td>
              </tr>
              <template v-if="plan">
                <tr data-rad="beraknat">
                  <th scope="row">Beräknat resultat</th>
                  <td class="num plan">{{ tal(planresultat, 'mnkr') }}</td>
                  <td v-for="f in j.forslag" :key="f.id" class="num">{{ tal(f.berakning?.beraknat ?? null, 'mnkr') }}</td>
                </tr>
                <tr data-rad="differens" class="summa">
                  <th scope="row">Differens</th>
                  <td class="num plan" />
                  <td v-for="f in j.forslag" :key="f.id" class="num" data-testid="resultatdifferens">
                    <template v-if="f.berakning?.differens != null">{{ talforandring(f.berakning.differens, 'mnkr') }}</template>
                    <span v-else class="saknas">–</span>
                  </td>
                </tr>
              </template>
            </tbody>
          </table>
        </div>
        <ul v-if="j.forslag.some((f) => f.anmarkning)" class="anmarkningar">
          <li v-for="f in j.forslag.filter((f) => f.anmarkning)" :key="f.id">
            <strong>{{ f.titel }}:</strong> {{ f.anmarkning }}
          </li>
        </ul>
        <p class="kallrad">
          Ramarna är nämndernas nettokostnad eller tilldelade skattemedel, som förslaget redovisar dem. En nämnd som
          förslaget inte tar upp räknas som oförändrad. Resultatet i mnkr är procenten av förslagets skatteintäkter och
          generella bidrag. Öppna en nämnd för att se förslagens åtgärder och satsningar, återgivna nära originalets
          text med sidan där de står.
        </p>
      </section>

      <section v-if="plan" class="kort" aria-labelledby="plan-rubrik" data-testid="planforutsattningar">
        <h2 id="plan-rubrik">Planförutsättningar {{ j.budgetar }}</h2>
        <p class="forklaring">
          Kommunens gemensamma utgångspunkt för budgetåret, före politiska prioriteringar. Den gäller alla förslag.
          Ett partis egna ändringar av investeringar, balans eller kassaflöde står som anmärkning till förslaget.
        </p>
        <div class="plantabeller">
          <table v-for="t in TABELLER" :key="t.nyckel" class="tabell plantabell" :data-tabell="t.nyckel">
            <caption>{{ t.rubrik }}, mnkr</caption>
            <tbody>
              <tr v-for="p in plan.tabeller[t.nyckel]" :key="p.post">
                <th scope="row">{{ p.post }}</th>
                <td class="num">{{ tal(p.mnkr, 'mnkr') }}</td>
                <td class="kalla">
                  <template v-for="(k, i) in p.kallor" :key="i"><template v-if="i">, </template><a v-if="k.forslag" :href="kallank(k)" target="_blank" rel="noopener">{{ k.text }}</a><template v-else>{{ k.text }}</template></template>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
        <p class="kallrad">Källa: förslagen och sidan där siffran står. Skattesats {{ skattesats(plan.skattesats.procent) }}.</p>
      </section>
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
  font-size: 13px;
  color: var(--ink-secondary);
  max-width: 70ch;
  margin: 0 0 12px;
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
  padding: 8px;
  border-bottom: 1px solid var(--line);
  vertical-align: top;
}
.tabell thead th {
  font-weight: 600;
  min-width: 130px;
}
.tabell tbody th {
  white-space: nowrap;
  font-weight: 600;
}
.tabell .num {
  text-align: right;
  font-variant-numeric: tabular-nums;
  white-space: nowrap;
}
.forslag {
  text-align: right !important;
}
.forslag > span,
.forslag > a {
  display: block;
}
.partier {
  display: flex !important;
  gap: 8px;
  justify-content: flex-end;
  flex-wrap: wrap;
}
.titel {
  font-weight: 400;
  color: var(--ink-secondary);
  white-space: normal;
}
.antagen {
  font-size: 12px;
  font-weight: 400;
  color: var(--ink-secondary);
}
.original {
  font-size: 12px;
  font-weight: 400;
}
.diff {
  display: block;
  font-size: 12px;
  color: var(--ink-secondary);
}
.vaxla {
  font: inherit;
  font-weight: 600;
  color: var(--accent);
  background: none;
  border: 0;
  padding: 0;
  cursor: pointer;
  text-align: left;
}
.atgarder td,
.atgarder th {
  font-size: 12px;
}
.atgardsrubrik {
  font-weight: 400 !important;
  color: var(--ink-secondary);
}
.atgardslista {
  list-style: none;
  margin: 0 0 4px;
  padding: 0;
  display: grid;
  gap: 6px;
  min-width: 180px;
  max-width: 280px;
}
.atgardstext {
  display: block;
  white-space: normal;
}
.atgardsbelopp {
  font-variant-numeric: tabular-nums;
  margin-right: 6px;
}
.sidlank {
  font-size: 12px;
}
.saknas {
  color: var(--ink-muted);
  font-style: italic;
}
.anmarkningar {
  font-size: 13px;
  color: var(--ink-secondary);
  margin: 12px 0 0;
  padding-left: 18px;
}
.plan {
  color: var(--ink-secondary);
}
.summa th,
.summa td {
  border-top: 1px solid var(--line-strong);
}
.plantabeller {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(320px, 1fr));
  gap: 16px 32px;
}
.plantabell caption {
  text-align: left;
  font-weight: 600;
  padding: 4px 0;
}
.plantabell tbody th {
  white-space: normal;
  font-weight: 400;
}
.kalla {
  font-size: 12px;
  color: var(--ink-muted);
  white-space: nowrap;
}
.kallrad {
  font-size: 12px;
  color: var(--ink-muted);
  margin: 8px 0 0;
}
.fel {
  color: var(--status-critical);
}
a {
  color: var(--accent);
}
</style>
