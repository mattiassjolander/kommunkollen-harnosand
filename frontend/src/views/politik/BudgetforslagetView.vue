<script setup lang="ts">
// Ett budgetförslag för sig (#147), öppnat från jämförelsen av förslagen: nyckeltal, redaktionens summering och
// grafer över hur förslaget fördelar ramarna mot planförutsättningarna.
// A: förändringen per nämnd, med ett streck för den antagna budgetens förändring (inte på den antagna budgetens
//    egen sida).
// B: brodiagram från planförutsättningarnas resultat via ramförändringarna och skatten till det beräknade
//    resultatet, och vidare via det som inte redovisas till förslagets budgeterade resultat.
// D: förslagets åtgärder per nämnd, med hur stor del av förändringen de förklarar.
// Bara budgetåret visas. En nämnd som förslaget inte anger står som "Anges inte" och räknas inte i B. Ett
// återkallat förslag visar en notis och inga grafer, och ett förslag som inte är publicerat finns inte för läsaren.
// Sidan läser jämförelsen för budgetåret och väljer förslaget efter nyckeln.
import { computed, inject, ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import { EjInloggad, hamtaBudget, type Budgetforslag, type Budgetjamforelse } from '../../api'
import { laddaNer } from '../../analys'
import { datum, siffra, tal, talforandring } from '../../format'
import { dokumenttitel } from '../../navigering'
import Partimarkering from '../../components/Partimarkering.vue'
import Brodiagram, { type Brosteg } from '../../components/Brodiagram.vue'
import Forandringsdiagram, { type Forandringsrad } from '../../components/Forandringsdiagram.vue'

const route = useRoute()
const utloggad = inject<() => void>('utloggad', () => {})

const ar = computed(() => Number(route.params.ar))
const nyckel = computed(() => String(route.params.nyckel))
const j = ref<Budgetjamforelse | null>(null)
const laddar = ref(true)
const fel = ref<string | null>(null)
const saknas = ref(false)

async function ladda() {
  laddar.value = true
  fel.value = null
  saknas.value = false
  j.value = null
  try {
    j.value = await hamtaBudget(ar.value)
  } catch (e) {
    if (e instanceof EjInloggad) return utloggad()
    if (e instanceof Error && e.message === 'API-fel 404') saknas.value = true
    else fel.value = e instanceof Error ? e.message : String(e)
  } finally {
    laddar.value = false
  }
}
watch(ar, ladda, { immediate: true })

const f = computed(() => j.value?.forslag.find((x) => x.nyckel === nyckel.value) ?? null)
const aterkallat = computed(() => j.value?.aterkallat.forslag.find((x) => x.nyckel === nyckel.value) ?? null)
const andra = computed(() => j.value?.forslag.filter((x) => x.nyckel !== nyckel.value) ?? [])
const plan = computed(() => j.value?.planforutsattningar ?? null)
const antagen = computed(() => j.value?.forslag.find((x) => x.id === j.value?.antagen) ?? null)
// Strecket för den antagna budgeten, utom på dess egen sida.
const streck = computed(() => !!antagen.value?.berakning?.planforutsattningar && antagen.value.id !== f.value?.id)
const b = computed(() => f.value?.berakning ?? null)
const medPlan = computed(() => !!b.value?.planforutsattningar)

watch(
  () => f.value?.titel ?? aterkallat.value?.titel,
  (t) => {
    if (t) document.title = dokumenttitel(route.path, t)
  },
)

const partitext = (p: string[]) => (p.length > 1 ? `${p.slice(0, -1).join(', ')} och ${p[p.length - 1]}` : (p[0] ?? ''))
const lank = (x: Budgetforslag, s?: number) =>
  s ? { href: `${x.original}#page=${s}`, target: '_blank', rel: 'noopener', title: `Sidan ${s}` } : {}
const sidtext = (x: Budgetforslag, s?: number) => (s ? `${x.titel}, s. ${s}` : x.titel)

const tvadecimaler = new Intl.NumberFormat('sv-SE', { minimumFractionDigits: 2, maximumFractionDigits: 2 })
const skattesats = (v: number) => `${tvadecimaler.format(v)} %`
const ore = (v: number) => (v === 0 ? 'oförändrad' : `${v > 0 ? '+' : '−'}${Math.abs(v)} öre`)
/** Ett belopp i mnkr utan enhet, med en decimal: "1,3". */
const belopp = (v: number) => tal(v, 'mnkr').replace(/ mnkr$/, '')

const ram = (o: string) => f.value?.uppgifter.ramar.find((r) => r.organ === o) ?? null
const berakning = (o: string) => b.value?.ramar.find((r) => r.organ === o) ?? null

// A: en rad per nämnd, från största ökning till största minskning. Nämnder som förslaget inte anger står sist.
const forandringsrader = computed<Forandringsrad[]>(() => {
  if (!j.value || !f.value || !medPlan.value) return []
  const x = f.value
  const rader = j.value.organ.map((o) => {
    const r = berakning(o)
    return {
      organ: o,
      forandring: r?.forandring ?? null,
      ram: r?.mnkr ?? null,
      plan: r?.plan ?? null,
      antagen: antagen.value?.berakning?.ramar.find((a) => a.organ === o)?.forandring ?? null,
      saknas: r && r.forandring === null ? 'Saknas i planförutsättningarna' : undefined,
      kalla: r ? `${sidtext(x, ram(o)?.sida)}. Planförutsättningar ${ar.value}.` : `${x.titel}.`,
    }
  })
  return rader.sort((p, q) => (q.forandring ?? -Infinity) - (p.forandring ?? -Infinity))
})

// B: stegen i samma ordning som i A. En högre ram ger ett lägre resultat.
const brosteg = computed<Brosteg[]>(() => {
  const x = f.value
  const c = b.value
  if (!x || !c || !medPlan.value) return []
  const steg: Brosteg[] = [
    {
      id: 'plan',
      titel: 'Resultat i planförutsättningarna',
      varde: c.plan_resultat,
      typ: 'summa',
      kalla: `Planförutsättningar ${ar.value}, resultatbudget`,
    },
  ]
  for (const r of forandringsrader.value) {
    if (r.forandring === null) continue
    steg.push({ id: `ram-${r.organ}`, titel: r.organ, varde: -r.forandring, typ: 'del', kalla: r.kalla })
  }
  steg.push(
    {
      id: 'skatt',
      titel: 'Skattesats',
      varde: c.skattejustering,
      typ: 'del',
      kalla: `${sidtext(x, x.uppgifter.skattesats.sida)}. Skatteintäkternas förändring räknad av Kommunkollen.`,
      markering: c.skattesats.ore !== null ? ore(c.skattesats.ore) : undefined,
    },
    { id: 'beraknat', titel: 'Beräknat resultat', varde: c.beraknat, typ: 'summa', kalla: 'Räknat av Kommunkollen' },
    {
      id: 'ej-redovisat',
      titel: 'Ej redovisat',
      varde: c.differens,
      typ: 'del',
      kalla: 'Förslagets budgeterade resultat minus det beräknade, räknat av Kommunkollen',
    },
    {
      id: 'budgeterat',
      titel: 'Budgeterat resultat',
      varde: c.resultat?.mnkr ?? null,
      typ: 'summa',
      kalla: sidtext(x, x.uppgifter.resultat?.sida),
    },
  )
  return steg
})
// Textalternativ till brodiagrammet: hela räkningen i en mening.
const brotext = computed(() => {
  const s = brosteg.value
  if (!s.length) return ''
  const del = (t: Brosteg) =>
    t.varde === null ? `${t.titel.toLowerCase()} uppgift saknas` : `${t.varde < 0 ? 'minus' : 'plus'} ${t.titel} ${tal(Math.abs(t.varde), 'mnkr')}`
  const ramar = s.filter((t) => t.id.startsWith('ram-') || t.id === 'skatt').map(del)
  const sist = s.slice(-2)
  return (
    `Resultatet i planförutsättningarna ${tal(s[0].varde, 'mnkr')}, ${ramar.join(', ')}, ger det beräknade resultatet ` +
    `${tal(b.value!.beraknat, 'mnkr')}. ${sist[0].titel} ${talforandring(sist[0].varde, 'mnkr')} ger det budgeterade ` +
    `resultatet ${tal(sist[1].varde, 'mnkr')}.`
  )
})

// D: åtgärderna per nämnd, sorterade efter förändringens storlek.
interface Namndatgarder {
  organ: string
  anges: boolean
  forandring: number | null
  atgarder: { text: string; mnkr?: number; sida?: number }[]
  tackning: string
}
const atgardsrader = computed<Namndatgarder[]>(() => {
  if (!j.value || !f.value) return []
  const rader = j.value.organ.map((o): Namndatgarder => {
    const r = ram(o)
    const c = berakning(o)
    const forandring = c?.forandring ?? null
    if (!r) return { organ: o, anges: false, forandring: null, atgarder: [], tackning: 'Anges inte' }
    const a = r.atgarder
    let tackning: string
    if (a === undefined) tackning = 'Åtgärderna är inte avlästa'
    else if (!a.length) tackning = 'Inga åtgärder anges'
    else if (!a.some((x) => x.mnkr !== undefined)) tackning = 'inga belopp angivna'
    else {
      const summa = a.reduce((s, x) => s + (x.mnkr ?? 0), 0)
      tackning =
        forandring !== null
          ? `åtgärderna förklarar ${belopp(summa)} av ${tal(forandring, 'mnkr')}`
          : `åtgärderna anger ${tal(summa, 'mnkr')}`
    }
    return { organ: o, anges: true, forandring, atgarder: a ?? [], tackning }
  })
  const storlek = (r: Namndatgarder) => (r.anges ? Math.abs(r.forandring ?? 0) : -1)
  return rader.sort((p, q) => storlek(q) - storlek(p))
})

// Tabellvy för graferna.
const vyA = ref<'diagram' | 'tabell'>('diagram')
const vyB = ref<'diagram' | 'tabell'>('diagram')

const cell = (v: string | number | null) =>
  v === null ? '' : typeof v === 'number' ? String(v).replace('.', ',') : v.includes(';') ? `"${v}"` : v
function exporteraA() {
  const rader = ['Nämnd;Budgetår;Förändring mnkr;Ram mnkr;Planförutsättningar mnkr;Antagen budget förändring mnkr;Källa']
  for (const r of forandringsrader.value)
    rader.push(
      [r.organ, ar.value, r.forandring ?? 'Anges inte', r.ram, r.plan, streck.value ? r.antagen : null, r.kalla].map(cell).join(';'),
    )
  laddaNer(`kommunkollen-budgetforslag-${ar.value}-${nyckel.value}-forandring.csv`, rader.join('\r\n') + '\r\n')
}
function exporteraB() {
  const rader = ['Steg;Budgetår;Värde mnkr;Typ;Källa']
  for (const s of brosteg.value) rader.push([s.titel, ar.value, s.varde, s.typ, s.kalla].map(cell).join(';'))
  laddaNer(`kommunkollen-budgetforslag-${ar.value}-${nyckel.value}-resultat.csv`, rader.join('\r\n') + '\r\n')
}
</script>

<template>
  <p v-if="fel" class="fel" role="alert">{{ fel }}</p>
  <p v-else-if="laddar">Hämtar budgetförslaget…</p>
  <template v-else-if="j && (f || aterkallat)">
    <nav class="byt" :aria-label="`Budgetförslag ${ar}`" data-testid="byt-forslag">
      <RouterLink
        v-for="x in andra"
        :key="x.id"
        :to="`/politik/budget/${ar}/${x.nyckel}`"
        class="annat"
        :data-nyckel="x.nyckel"
      >
        <span class="prickar"><Partimarkering v-for="p in x.partier" :key="p" :parti="p" /></span>
        {{ x.antagen ? 'Antagen budget' : x.titel }}
      </RouterLink>
      <RouterLink :to="`/politik/budget?ar=${ar}`" class="alla" data-testid="alla-budgetforslag">Alla budgetförslag {{ ar }}</RouterLink>
    </nav>

    <!-- Återkallat för rättning: samma notis som i jämförelsen, och inga grafer. -->
    <template v-if="!f && aterkallat">
      <header class="vyhuvud">
        <span class="partier"><Partimarkering v-for="p in aterkallat.partier" :key="p" :parti="p" /></span>
        <h1>{{ aterkallat.titel }}</h1>
      </header>
      <p class="notis" data-testid="aterkallat-forslag">
        {{ aterkallat.typ === 'tillagg' ? 'Tilläggsförslaget' : 'Förslaget' }} från {{ partitext(aterkallat.partier) }} är tillbakadraget för rättning.
      </p>
    </template>

    <template v-else-if="f">
      <header class="vyhuvud" data-testid="forslagshuvud" :data-nyckel="f.nyckel">
        <span class="partier"><Partimarkering v-for="p in f.partier" :key="p" :parti="p" /></span>
        <h1>{{ f.titel }}</h1>
        <p class="meta">
          <span v-if="f.antagen" class="etikett" data-testid="antagen">Antagen budget</span>
          <span v-if="f.typ === 'tillagg'" class="etikett">Tilläggsbudget</span>
          <span v-if="f.andring" class="etikett">Ändrad efter publicering {{ datum(f.andring.publicerad) }}</span>
          <span v-if="f.publicerad">Publicerad {{ datum(f.publicerad) }}</span>
          <a :href="f.original" target="_blank" rel="noopener" data-testid="originalet">Originalet</a>
        </p>
      </header>

      <section class="kort" aria-labelledby="nyckeltal-rubrik" data-testid="nyckeltal">
        <h2 id="nyckeltal-rubrik">Budgetår {{ ar }}</h2>
        <dl class="nyckeltal">
          <div v-if="medPlan" data-nyckeltal="forandring">
            <dt>Förändring av ramarna</dt>
            <dd class="stort">{{ talforandring(b!.forandring, 'mnkr') }}</dd>
            <dd class="under">mot planförutsättningarna</dd>
          </div>
          <div data-nyckeltal="skattesats">
            <dt>Skattesats</dt>
            <template v-if="b?.skattesats.procent != null">
              <dd class="stort">
                <component :is="f.uppgifter.skattesats.sida ? 'a' : 'span'" v-bind="lank(f, f.uppgifter.skattesats.sida)">{{ skattesats(b.skattesats.procent) }}</component>
              </dd>
              <dd v-if="b.skattesats.ore !== null" class="under">
                {{ ore(b.skattesats.ore) }}<template v-if="b.skattejustering">, skatteintäkter {{ talforandring(b.skattejustering, 'mnkr') }}</template>
              </dd>
            </template>
            <dd v-else class="stort saknas">Anges inte</dd>
          </div>
          <div data-nyckeltal="resultat">
            <dt>Budgeterat resultat</dt>
            <template v-if="b?.resultat">
              <dd class="stort">
                <component :is="f.uppgifter.resultat?.sida ? 'a' : 'span'" v-bind="lank(f, f.uppgifter.resultat?.sida)">
                  {{ b.resultat.mnkr !== null ? tal(b.resultat.mnkr, 'mnkr') : tal(b.resultat.procent, '%') }}
                </component>
              </dd>
              <dd v-if="b.resultat.mnkr !== null" class="under">{{ tal(b.resultat.procent, '%') }} av skatter och bidrag</dd>
            </template>
            <dd v-else class="stort saknas">Anges inte</dd>
          </div>
          <div v-if="medPlan" data-nyckeltal="differens">
            <dt>Differens mot beräknat resultat</dt>
            <dd class="stort">
              <template v-if="b!.differens !== null">{{ talforandring(b!.differens, 'mnkr') }}</template>
              <span v-else class="saknas">Uppgift saknas</span>
            </dd>
            <dd class="under">beräknat resultat {{ tal(b!.beraknat, 'mnkr') }}</dd>
          </div>
        </dl>
        <p v-if="!medPlan" class="forklaring" data-testid="utan-planforutsattningar">
          Planförutsättningarna för {{ ar }} finns inte här, så förslaget visas utan förändring mot planförutsättningarna
          och utan beräknat resultat.
        </p>
        <p v-if="f.anmarkning" class="forklaring">{{ f.anmarkning }}</p>
        <p class="kallrad">
          Källa: förslaget och planförutsättningarna för {{ ar }}. Förändringen, skatteintäkternas förändring och det
          beräknade resultatet är räknade av Kommunkollen.
        </p>
      </section>

      <section v-if="f.summering" class="kort analys" aria-labelledby="summering-rubrik" data-testid="summering">
        <h2 id="summering-rubrik">Summering <span class="analysetikett">Analys</span></h2>
        <p class="forklaring">
          Redaktionens sammanfattning av förslaget, med samma frågor för alla förslag. Svaren återger vad förslaget säger,
          med sidan där det står, och värderar det inte.
        </p>
        <dl class="summering">
          <div v-for="q in f.summering" :key="q.id" :data-fraga="q.id">
            <dt>{{ q.fraga }}</dt>
            <dd v-if="q.anges_inte" class="saknas">Förslaget tar inte upp frågan</dd>
            <dd v-else>
              {{ q.text }}
              <a v-for="s in q.sidor ?? []" :key="s" v-bind="lank(f, s)" class="sidlank">s. {{ s }}</a>
            </dd>
          </div>
        </dl>
      </section>

      <template v-if="medPlan">
        <section class="kort" aria-labelledby="graf-a-rubrik" data-testid="graf-forandring">
          <div class="korthuvud">
            <h2 id="graf-a-rubrik">Förändring mot planförutsättningarna per nämnd</h2>
            <div class="vaxel" role="group" aria-label="Visa förändringen som">
              <button type="button" :aria-pressed="vyA === 'diagram'" @click="vyA = 'diagram'">Diagram</button>
              <button type="button" :aria-pressed="vyA === 'tabell'" @click="vyA = 'tabell'">Tabell</button>
            </div>
          </div>
          <p class="forklaring">
            Förslagets ram minus planförutsättningarnas ram för varje nämnd, i mnkr, från största ökning till största
            minskning.<template v-if="streck"> Strecket visar den antagna budgetens förändring för samma nämnd.</template>
          </p>
          <Forandringsdiagram v-if="vyA === 'diagram'" :rader="forandringsrader" :streck="streck" :period="String(ar)" />
          <table v-else class="tabell" data-testid="tabell-forandring">
            <caption class="dold">Förändring mot planförutsättningarna per nämnd {{ ar }}, mnkr</caption>
            <thead>
              <tr>
                <th scope="col">Nämnd</th>
                <th scope="col" class="num">Ram</th>
                <th scope="col" class="num">Planförutsättningar</th>
                <th scope="col" class="num">Förändring</th>
                <th v-if="streck" scope="col" class="num">Antagen budget</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="r in forandringsrader" :key="r.organ">
                <th scope="row">{{ r.organ }}</th>
                <template v-if="r.forandring !== null || r.ram !== null">
                  <td class="num">{{ tal(r.ram, 'mnkr') }}</td>
                  <td class="num">{{ tal(r.plan, 'mnkr') }}</td>
                  <td class="num">{{ talforandring(r.forandring, 'mnkr') }}</td>
                </template>
                <td v-else colspan="3" class="saknas">Anges inte</td>
                <td v-if="streck" class="num">{{ r.antagen !== null ? talforandring(r.antagen, 'mnkr') : '–' }}</td>
              </tr>
            </tbody>
          </table>
          <div class="fot">
            <p class="kallrad">Källa: förslaget och planförutsättningarna för {{ ar }}. Förändringen är räknad av Kommunkollen.</p>
            <button type="button" class="csv" data-testid="csv-forandring" @click="exporteraA">CSV</button>
          </div>
        </section>

        <section class="kort" aria-labelledby="graf-b-rubrik" data-testid="graf-resultat">
          <div class="korthuvud">
            <h2 id="graf-b-rubrik">Från planförutsättningarnas resultat till förslagets</h2>
            <div class="vaxel" role="group" aria-label="Visa resultatet som">
              <button type="button" :aria-pressed="vyB === 'diagram'" @click="vyB = 'diagram'">Diagram</button>
              <button type="button" :aria-pressed="vyB === 'tabell'" @click="vyB = 'tabell'">Tabell</button>
            </div>
          </div>
          <p class="forklaring">
            Planförutsättningarnas resultat, minus förslagets förändring av varje ram och plus skatteintäkternas
            förändring, blir det beräknade resultatet. En högre ram ger ett lägre resultat. Ej redovisat är skillnaden
            mellan det beräknade resultatet och förslagets budgeterade resultat, som förslaget saknar finansiering för
            eller inte redovisar. Nämnder som förslaget inte anger räknas inte.
          </p>
          <p class="dold" data-testid="brotext">{{ brotext }}</p>
          <Brodiagram v-if="vyB === 'diagram'" :steg="brosteg" enhet="mnkr" :period="String(ar)" staende />
          <table v-else class="tabell" data-testid="tabell-resultat">
            <caption class="dold">Från planförutsättningarnas resultat till förslagets {{ ar }}, mnkr</caption>
            <thead>
              <tr>
                <th scope="col">Steg</th>
                <th scope="col" class="num">Mnkr</th>
                <th scope="col">Källa</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="s in brosteg" :key="s.id" :class="{ summa: s.typ === 'summa' }">
                <th scope="row">{{ s.titel }} <span v-if="s.markering" class="markering">{{ s.markering }}</span></th>
                <td class="num">{{ s.typ === 'summa' ? siffra(s.varde, 'mnkr') : talforandring(s.varde, 'mnkr') }}</td>
                <td class="kalla">{{ s.kalla }}</td>
              </tr>
            </tbody>
          </table>
          <div class="fot">
            <p class="kallrad">
              Källa: förslaget och planförutsättningarna för {{ ar }}. Skatteintäkternas förändring och det beräknade
              resultatet är räknade av Kommunkollen.
            </p>
            <button type="button" class="csv" data-testid="csv-resultat" @click="exporteraB">CSV</button>
          </div>
        </section>
      </template>

      <section class="kort" aria-labelledby="graf-d-rubrik" data-testid="atgarder-per-namnd">
        <h2 id="graf-d-rubrik">Åtgärder per nämnd</h2>
        <p class="forklaring">
          Förslagets besparingar och satsningar för varje ram, återgivna nära originalets text med sidan där de står.
          Nämnderna står efter hur mycket ramen ändras.
        </p>
        <ul class="namnder">
          <li v-for="r in atgardsrader" :key="r.organ" :data-organ="r.organ" :class="{ anges: !r.anges }" data-testid="namndatgarder">
            <h3>
              {{ r.organ }}
              <span v-if="r.anges && r.forandring !== null" class="forandringstal">{{ talforandring(r.forandring, 'mnkr') }}</span>
            </h3>
            <ul v-if="r.atgarder.length" class="atgardslista">
              <li v-for="(a, i) in r.atgarder" :key="i" data-testid="atgard">
                <span class="atgardstext">{{ a.text }}</span>
                <span v-if="a.mnkr !== undefined" class="atgardsbelopp">{{ talforandring(a.mnkr, 'mnkr') }}</span>
                <a v-if="a.sida" v-bind="lank(f, a.sida)" class="sidlank">s. {{ a.sida }}</a>
              </li>
            </ul>
            <p class="tackning" :class="{ saknas: !r.anges || !r.atgarder.length }" data-testid="tackning">{{ r.tackning }}</p>
          </li>
        </ul>
        <p class="kallrad">Källa: {{ f.titel }}. Täckningen är summan av åtgärdernas belopp mot förändringen.</p>
      </section>
    </template>
  </template>
  <template v-else>
    <header class="vyhuvud"><h1>Sidan finns inte</h1></header>
    <p class="saknas-sida" data-testid="sidan-finns-inte">
      Det finns inget publicerat budgetförslag med den adressen.
      <RouterLink :to="`/politik/budget${ar ? `?ar=${ar}` : ''}`">Alla budgetförslag</RouterLink>
    </p>
  </template>
</template>

<style scoped>
.byt {
  display: flex;
  flex-wrap: wrap;
  gap: 8px 16px;
  align-items: center;
  font-size: 13px;
  margin-bottom: 16px;
}
.byt a {
  color: var(--accent);
}
.annat {
  display: inline-flex;
  align-items: center;
  gap: 6px;
}
.prickar {
  display: inline-flex;
  gap: 6px;
  color: var(--ink-secondary);
}
.alla {
  margin-left: auto;
}
.vyhuvud {
  margin-bottom: 16px;
}
.vyhuvud h1 {
  margin: 4px 0;
}
.partier {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
  font-size: 13px;
}
.meta {
  display: flex;
  flex-wrap: wrap;
  gap: 4px 12px;
  align-items: center;
  margin: 0;
  font-size: 13px;
  color: var(--ink-secondary);
}
.etikett {
  font-size: 12px;
  border: 1px solid var(--line-strong);
  border-radius: var(--radius);
  padding: 0 6px;
}
.kort {
  background: var(--surface);
  border: 1px solid var(--line);
  border-radius: var(--radius);
  padding: 16px 24px;
  margin-bottom: 16px;
  min-width: 0;
}
.kort h2 {
  font-size: 15px;
  margin: 0 0 8px;
}
.korthuvud {
  display: flex;
  flex-wrap: wrap;
  justify-content: space-between;
  align-items: flex-start;
  gap: 8px 12px;
}
.nyckeltal {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
  gap: 16px 24px;
  margin: 8px 0 12px;
}
.nyckeltal dt {
  font-size: 13px;
  color: var(--ink-secondary);
}
.nyckeltal dd {
  margin: 0;
}
.stort {
  font-size: 32px;
  font-weight: 600;
  line-height: 1.2;
}
.stort a {
  color: var(--ink);
  text-decoration-color: var(--line-strong);
}
.under {
  font-size: 12px;
  color: var(--ink-muted);
}
.notis {
  font-size: 13px;
  max-width: 70ch;
  margin: 0 0 12px;
  padding: 6px 10px;
  border: 1px solid var(--line-strong);
  border-radius: var(--radius);
}
.forklaring {
  font-size: 13px;
  color: var(--ink-secondary);
  max-width: 70ch;
  margin: 0 0 12px;
}
.analys {
  border-style: dashed;
  border-color: var(--line-strong);
}
.analysetikett {
  font-size: 12px;
  font-weight: 600;
  color: var(--ink-secondary);
  border: 1px dashed var(--line-strong);
  border-radius: var(--radius);
  padding: 0 6px;
  margin-left: 6px;
}
.summering {
  display: grid;
  gap: 8px;
  margin: 0;
  font-size: 13px;
  max-width: 80ch;
}
.summering dt {
  font-weight: 600;
}
.summering dd {
  margin: 0;
}
.sidlank {
  font-size: 12px;
  margin-left: 6px;
}
.vaxel {
  display: inline-flex;
  border: 1px solid var(--line-strong);
  border-radius: var(--radius);
  overflow: hidden;
}
.vaxel button {
  font: inherit;
  font-size: 12px;
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
  vertical-align: top;
}
.tabell thead th {
  font-weight: 600;
  color: var(--ink-secondary);
}
.tabell tbody th {
  font-weight: 400;
}
.tabell .num {
  text-align: right;
  font-variant-numeric: tabular-nums;
  white-space: nowrap;
}
.tabell tr.summa th,
.tabell tr.summa td {
  font-weight: 600;
  border-top: 1px solid var(--line-strong);
}
.markering {
  display: block;
  font-size: 11px;
  color: var(--ink-muted);
}
.kalla {
  font-size: 12px;
  color: var(--ink-muted);
}
.fot {
  display: flex;
  justify-content: space-between;
  align-items: flex-end;
  gap: 12px;
}
.csv {
  flex-shrink: 0;
  font: inherit;
  font-size: 12px;
  padding: 2px 8px;
  border: 1px solid var(--line-strong);
  border-radius: var(--radius);
  background: var(--surface-raised);
  color: var(--ink-secondary);
  cursor: pointer;
}
.namnder {
  list-style: none;
  margin: 0;
  padding: 0;
  display: grid;
  gap: 4px;
}
.namnder > li {
  padding: 8px 0;
  border-bottom: 1px solid var(--line);
}
.namnder h3 {
  display: flex;
  justify-content: space-between;
  gap: 12px;
  font-size: 14px;
  margin: 0 0 4px;
}
.namnder > li.anges h3 {
  color: var(--ink-muted);
  font-weight: 400;
}
.forandringstal {
  font-variant-numeric: tabular-nums;
  white-space: nowrap;
}
.atgardslista {
  list-style: none;
  margin: 0 0 4px;
  padding: 0;
  display: grid;
  gap: 4px;
  font-size: 13px;
  max-width: 80ch;
}
.atgardsbelopp {
  font-variant-numeric: tabular-nums;
  margin-left: 6px;
  color: var(--ink-secondary);
}
.tackning {
  font-size: 12px;
  color: var(--ink-secondary);
  margin: 0;
}
.saknas {
  color: var(--ink-muted);
  font-style: italic;
}
.kallrad {
  font-size: 12px;
  color: var(--ink-muted);
  margin: 12px 0 0;
}
.fel {
  color: var(--status-critical);
}
a {
  color: var(--accent);
}
.dold {
  position: absolute;
  width: 1px;
  height: 1px;
  overflow: hidden;
  clip: rect(0 0 0 0);
}
</style>
