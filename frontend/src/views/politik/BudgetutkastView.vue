<script setup lang="ts">
// Budgetförslag och planförutsättningar som utkast (#48, #58): redaktören rättar förslagens siffror mot
// originalet, och en utgivare som inte läst in eller ändrat uppgifterna granskar och publicerar dem
// (kravspec 18, ADR-0002). Planförutsättningarna rättas i Excelfilen och läses in på nytt.
// Varje ram kan ha åtgärder och satsningar med belopp och sida (#57), som granskas med förslaget.
// Redaktören anger behandlingen där förslaget ställdes och skriver summeringen med samma frågor för alla
// förslag (#48). Summeringen märks Analys.
import { computed, inject, onMounted, reactive, ref, type Ref } from 'vue'
import {
  EjInloggad,
  andraBudgetforslag,
  granskaBudgetforslag,
  granskaPlanforutsattningar,
  hamtaBudgetutkast,
  hamtaPlanutkast,
  publiceraBudgetforslag,
  publiceraPlanforutsattningar,
  type Budgetuppgifterin,
  type Summeringssvar,
  type Budgetutkast,
  type Jag,
  type Kalla,
  type Plantabell,
  type Planutkast,
} from '../../api'
import { datumTid } from '../../format'
import Partimarkering from '../../components/Partimarkering.vue'
import PolitikFlikar from '../../components/PolitikFlikar.vue'

const utloggad = inject<() => void>('utloggad', () => {})
const jag = inject<Ref<Jag | null>>('jag', ref(null))
const arRedaktor = computed(() => jag.value?.roller.includes('redaktor') ?? false)
const arUtgivare = computed(() => jag.value?.roller.includes('utgivare') ?? false)

const lista = ref<Budgetutkast[]>([])
const planer = ref<Planutkast[]>([])
const laddar = ref(true)
const fel = ref<string | null>(null)
const oppen = ref<number | null>(null)
const meddelande = reactive<Record<string, string>>({})

interface Formular {
  titel: string
  partier: string
  antagen: boolean
  anmarkning: string
  skatt: { ore: string; sida: string }
  resultat: { procent: string; sida: string }
  ramar: { organ: string; mnkr: string; forandring: string; sida: string; atgarder: Atgardsfalt[] }[]
  behandling: { organ: string; datum: string; paragraf: string }
  summering: Record<string, Svarsfalt>
}
interface Svarsfalt {
  text: string
  sidor: string
  anges_inte: boolean
}
interface Atgardsfalt {
  text: string
  mnkr: string
  sida: string
}
const form = ref<Formular | null>(null)

async function ladda() {
  laddar.value = true
  fel.value = null
  try {
    const [utkast, granskade, pu, pg] = await Promise.all([
      hamtaBudgetutkast('utkast'),
      hamtaBudgetutkast('granskad'),
      hamtaPlanutkast('utkast'),
      hamtaPlanutkast('granskad'),
    ])
    lista.value = [...utkast, ...granskade].sort((a, b) => b.budgetar - a.budgetar || a.nyckel.localeCompare(b.nyckel))
    planer.value = [...pu, ...pg].sort((a, b) => b.budgetar - a.budgetar)
  } catch (e) {
    if (e instanceof EjInloggad) return utloggad()
    fel.value = e instanceof Error ? e.message : String(e)
  } finally {
    laddar.value = false
  }
}
onMounted(ladda)

const s = (v: number | undefined | null) => (v === undefined || v === null ? '' : String(v))
function oppna(f: Budgetutkast) {
  oppen.value = f.id
  const u = f.uppgifter
  form.value = {
    titel: f.titel,
    partier: f.partier.join(', '),
    antagen: f.antagen,
    anmarkning: f.anmarkning,
    skatt: { ore: s(u.skattesats.ore), sida: s(u.skattesats.sida) },
    resultat: { procent: s(u.resultat?.procent), sida: s(u.resultat?.sida) },
    ramar: u.ramar.map((r) => ({
      organ: r.organ,
      mnkr: s(r.mnkr),
      forandring: '',
      sida: s(r.sida),
      atgarder: (r.atgarder ?? []).map((a) => ({ text: a.text, mnkr: s(a.mnkr), sida: s(a.sida) })),
    })),
    behandling: { organ: u.behandling?.organ ?? 'KF', datum: u.behandling?.datum ?? '', paragraf: s(u.behandling?.paragraf) },
    summering: Object.fromEntries(
      f.mall.map((q) => {
        const v = u.summering?.[q.id]
        return [q.id, v && 'anges_inte' in v
          ? { text: '', sidor: '', anges_inte: true }
          : { text: v?.text ?? '', sidor: (v?.sidor ?? []).join(', '), anges_inte: false }]
      }),
    ),
  }
}

// Tal skrivs med komma eller punkt. Tomma fält skickas inte.
const tal = (v: string) => (v.trim() === '' ? undefined : Number(v.replace(/\s/g, '').replace(',', '.').replace('−', '-')))
function uppgifter(f: Formular, u: Budgetutkast['uppgifter']): Budgetuppgifterin {
  // Ett år utan planförutsättningar har skattesatsen i procent; den ändras inte här.
  const skatt = u.skattesats.procent !== undefined && !f.skatt.ore.trim()
    ? { procent: u.skattesats.procent, sida: tal(f.skatt.sida) }
    : { ore: tal(f.skatt.ore) ?? 0, sida: tal(f.skatt.sida) }
  return {
    skattesats: skatt,
    resultat: f.resultat.procent.trim() ? { procent: tal(f.resultat.procent)!, sida: tal(f.resultat.sida) } : null,
    ramar: f.ramar.map((r) => {
      const atgarder = r.atgarder.map((a) => ({ text: a.text, mnkr: tal(a.mnkr), sida: tal(a.sida) }))
      const ram = r.mnkr.trim()
        ? { organ: r.organ, mnkr: tal(r.mnkr), sida: tal(r.sida) }
        : { organ: r.organ, forandring: tal(r.forandring), sida: tal(r.sida) }
      return atgarder.length ? { ...ram, atgarder } : ram
    }),
    // Behandlingen skickas när datum eller paragraf är ifyllt, summeringen när något svar är ifyllt.
    ...(f.behandling.datum.trim() || f.behandling.paragraf.trim()
      ? { behandling: { organ: f.behandling.organ.trim() || 'KF', datum: f.behandling.datum.trim(), paragraf: tal(f.behandling.paragraf) } }
      : {}),
    ...(Object.values(f.summering).some((v) => v.anges_inte || v.text.trim())
      ? { summering: Object.fromEntries(Object.entries(f.summering).map(([id, v]): [string, Summeringssvar] => [id, v.anges_inte
          ? { anges_inte: true }
          : { text: v.text, sidor: v.sidor.split(/[,\s]+/).filter(Boolean).map(Number) }])) }
      : {}),
  }
}

async function steg<T extends { id: number; status: string }>(
  nyckel: string,
  lst: Ref<T[]>,
  id: number,
  gor: () => Promise<T>,
  klart: string,
) {
  meddelande[nyckel] = ''
  try {
    const ny = await gor()
    if (ny.status === 'publicerad') lst.value = lst.value.filter((x) => x.id !== id)
    else lst.value = lst.value.map((x) => (x.id === id ? ny : x))
    meddelande[nyckel] = klart
    if (ny.status !== 'utkast') oppen.value = null
  } catch (e) {
    if (e instanceof EjInloggad) return utloggad()
    meddelande[nyckel] = e instanceof Error ? e.message : String(e)
  }
}
const spara = (f: Budgetutkast) =>
  steg(
    `f${f.id}`,
    lista,
    f.id,
    () =>
      andraBudgetforslag(f.id, {
        titel: form.value!.titel,
        partier: form.value!.partier.split(/[,\s+]+/).filter(Boolean),
        antagen: form.value!.antagen,
        anmarkning: form.value!.anmarkning,
        uppgifter: uppgifter(form.value!, f.uppgifter),
      }),
    'Sparat som utkast.',
  )
const granska = (f: Budgetutkast) => steg(`f${f.id}`, lista, f.id, () => granskaBudgetforslag(f.id), 'Granskat.')
const publicera = (f: Budgetutkast) => steg(`f${f.id}`, lista, f.id, () => publiceraBudgetforslag(f.id), 'Publicerat.')
const granskaPlan = (p: Planutkast) => steg(`p${p.id}`, planer, p.id, () => granskaPlanforutsattningar(p.id), 'Granskat.')
const publiceraPlan = (p: Planutkast) =>
  steg(`p${p.id}`, planer, p.id, () => publiceraPlanforutsattningar(p.id), 'Publicerat.')
const andrat = (f: Budgetutkast) => JSON.stringify(f.uppgifter) !== JSON.stringify(f.inlast)
const egen = (f: { redaktorer: string[] }) => !!jag.value && f.redaktorer.includes(jag.value.epost)

// Granskningsvyn: siffrorna som de står i uppgifterna, utan avrundning, med sidan i originalet.
const exakt = new Intl.NumberFormat('sv-SE', { maximumFractionDigits: 3 })
const med = new Intl.NumberFormat('sv-SE', { maximumFractionDigits: 3, signDisplay: 'exceptZero' })
const nr = (v: number) => exakt.format(v)
const fr = (v: number) => (v === 0 ? '±0' : med.format(v))
const sidlank = (f: Budgetutkast, sida?: number) => (sida ? `${f.original}#page=${sida}` : null)
const forandring = (f: Budgetutkast, organ: string) => f.berakning?.ramar.find((r) => r.organ === organ)?.forandring ?? null
const tackning = (f: Budgetutkast, organ: string) => f.berakning?.ramar.find((r) => r.organ === organ)?.atgarder ?? null
const kallank = (k: Kalla) => `/api/budgetforslag/${k.forslag}/original#page=${k.sida}`

const TABELLER: { nyckel: Plantabell; rubrik: string }[] = [
  { nyckel: 'resultatbudget', rubrik: 'Resultatbudget' },
  { nyckel: 'namnder', rubrik: 'Nämnder' },
  { nyckel: 'investeringar', rubrik: 'Investeringar' },
  { nyckel: 'balansbudget', rubrik: 'Balansbudget' },
  { nyckel: 'kassaflode', rubrik: 'Kassaflöde' },
]
const kontroller = (p: Planutkast, t: Plantabell) => p.kontroller.filter((k) => k.tabell === t)
</script>

<template>
  <header class="vyhuvud">
    <h1>Politik och beslut</h1>
    <p class="ingress">
      Planförutsättningar och budgetförslag som lästs in och väntar på publicering. Kontrollera varje siffra mot sidan i
      originalet. En utgivare som inte läst in eller ändrat uppgifterna granskar och publicerar dem.
    </p>
  </header>
  <PolitikFlikar />

  <p v-if="fel" class="fel" role="alert">{{ fel }}</p>
  <p v-else-if="laddar">Hämtar utkast…</p>
  <p v-else-if="!lista.length && !planer.length" class="saknas" data-testid="inga-utkast">Inga budgetförslag väntar på publicering.</p>
  <template v-else>
    <section v-if="planer.length" aria-labelledby="planer-rubrik">
      <h2 id="planer-rubrik" class="sektion">Planförutsättningar</h2>
      <ul class="lista">
        <li v-for="p in planer" :key="p.id" class="kort" data-testid="planutkast" :data-budgetar="p.budgetar">
          <div class="huvud">
            <strong>Planförutsättningar {{ p.budgetar }}</strong>
            <span class="etikett" :data-status="p.status">{{ p.status === 'utkast' ? 'Utkast' : 'Granskad' }}</span>
            <span class="meta-inline">{{ p.filnamn }}, flik {{ p.budgetar }}</span>
          </div>
          <p class="meta">
            Läst in av {{ p.redaktorer.join(', ') }}, senast {{ datumTid(p.andrad) }}.
            <template v-if="p.granskad_av">Granskat av {{ p.granskad_av }}.</template>
            Rätta i Excelfilen och läs in den igen.
          </p>
          <p class="meta">
            <strong>Skattesats:</strong> {{ nr(p.skattesats.procent) }} % ({{ p.skattesats.kalla }})
          </p>
          <div class="plantabeller">
            <table v-for="t in TABELLER" :key="t.nyckel" class="ramtabell" :data-tabell="t.nyckel">
              <caption>{{ t.rubrik }}, mnkr</caption>
              <tbody>
                <tr v-for="x in p.tabeller[t.nyckel]" :key="x.post">
                  <th scope="row">{{ x.post }}</th>
                  <td class="num">{{ nr(x.mnkr) }}</td>
                  <td class="kalla">
                    <template v-for="(k, i) in x.kallor" :key="i"><template v-if="i">, </template><a v-if="k.forslag" :href="kallank(k)" target="_blank" rel="noopener">{{ k.text }}</a><template v-else>{{ k.text }}</template></template>
                  </td>
                </tr>
                <tr v-for="k in kontroller(p, t.nyckel)" :key="`k-${k.post}`" class="kontroll" data-testid="kontroll">
                  <th scope="row">Kontroll: {{ k.post }}</th>
                  <td class="num" :data-avviker="k.differens ? 'ja' : undefined">
                    <template v-if="k.procent !== undefined">{{ nr(k.procent) }} %</template>
                    <template v-else>{{ fr(k.differens!) }}</template>
                  </td>
                  <td class="kalla">
                    <template v-if="k.procent === undefined">summa {{ nr(k.summa!) }}, angivet {{ nr(k.angivet!) }}</template>
                    <template v-else>uträknat</template>
                  </td>
                </tr>
              </tbody>
            </table>
          </div>
          <p class="meta">Kontroll är det angivna beloppet minus summan av posterna. ±0 betyder att tabellen går ihop.</p>
          <div class="knappar">
            <button v-if="arUtgivare && p.status === 'utkast'" type="button" :disabled="egen(p)" :title="egen(p) ? 'Du har läst in planförutsättningarna' : ''" data-testid="granska" @click="granskaPlan(p)">Granska</button>
            <button v-if="arUtgivare && p.status === 'granskad'" type="button" :disabled="egen(p)" data-testid="publicera" @click="publiceraPlan(p)">Publicera</button>
            <span v-if="meddelande[`p${p.id}`]" class="meddelande" role="status">{{ meddelande[`p${p.id}`] }}</span>
          </div>
        </li>
      </ul>
    </section>

    <section v-if="lista.length" aria-labelledby="forslag-rubrik">
      <h2 id="forslag-rubrik" class="sektion">Budgetförslag</h2>
      <ul class="lista">
        <li v-for="f in lista" :key="f.id" class="kort" data-testid="budgetutkast" :data-nyckel="f.nyckel">
          <div class="huvud">
            <strong>{{ f.budgetar }}</strong>
            <span class="partier"><Partimarkering v-for="p in f.partier" :key="p" :parti="p" /></span>
            <span>{{ f.titel }}</span>
            <span v-if="f.antagen" class="etikett">Antagen budget</span>
            <span class="etikett" :data-status="f.status">{{ f.status === 'utkast' ? 'Utkast' : 'Granskad' }}</span>
            <a :href="f.original" target="_blank" rel="noopener">{{ f.filnamn }}</a>
          </div>
          <p class="meta">
            Läst in eller ändrat av {{ f.redaktorer.join(', ') }}, senast {{ datumTid(f.andrad) }}.
            <template v-if="f.granskad_av">Granskat av {{ f.granskad_av }}.</template>
            <template v-if="andrat(f)"> Ändrat sedan inläsningen.</template>
          </p>
          <p v-if="f.anmarkning" class="meta">{{ f.anmarkning }}</p>

          <div v-if="oppen !== f.id" class="uppgifter" data-testid="uppgifter">
            <p>
              <strong>Skattesats:</strong>
              <template v-if="f.uppgifter.skattesats.procent !== undefined"> {{ nr(f.uppgifter.skattesats.procent) }} %</template>
              <template v-else-if="f.uppgifter.skattesats.ore"> {{ fr(f.uppgifter.skattesats.ore) }} öre</template>
              <template v-else> oförändrad</template>
              <a v-if="sidlank(f, f.uppgifter.skattesats.sida)" :href="sidlank(f, f.uppgifter.skattesats.sida)!" target="_blank" rel="noopener" class="sida">s. {{ f.uppgifter.skattesats.sida }}</a>
            </p>
            <p>
              <strong>Budgeterat resultat:</strong>
              <template v-if="f.uppgifter.resultat">
                {{ nr(f.uppgifter.resultat.procent) }} %
                <template v-if="f.berakning?.resultat?.mnkr != null">({{ nr(f.berakning.resultat.mnkr) }} mnkr)</template>
                <a v-if="sidlank(f, f.uppgifter.resultat.sida)" :href="sidlank(f, f.uppgifter.resultat.sida)!" target="_blank" rel="noopener" class="sida">s. {{ f.uppgifter.resultat.sida }}</a>
              </template>
              <span v-else class="saknas"> anges inte</span>
            </p>
            <p v-if="f.berakning?.planforutsattningar" data-testid="beraknat">
              <strong>Beräknat resultat:</strong> {{ nr(f.berakning.beraknat!) }} mnkr
              <template v-if="f.berakning.differens !== null">· differens {{ fr(f.berakning.differens) }} mnkr</template>
            </p>
            <p v-else class="saknas">Planförutsättningar för {{ f.budgetar }} saknas, så ingen förändring räknas.</p>
            <table v-if="f.uppgifter.ramar.length" class="ramtabell">
              <caption>Ramar per nämnd {{ f.budgetar }}, mnkr (förändring mot planförutsättningarna inom parentes), med åtgärder</caption>
              <tbody>
                <template v-for="r in f.uppgifter.ramar" :key="r.organ">
                  <tr>
                    <th scope="row">{{ r.organ }}</th>
                    <td class="num">
                      {{ nr(r.mnkr) }}<template v-if="forandring(f, r.organ) !== null"> ({{ fr(forandring(f, r.organ)!) }})</template>
                      <a v-if="sidlank(f, r.sida)" :href="sidlank(f, r.sida)!" target="_blank" rel="noopener" class="sida">s. {{ r.sida }}</a>
                    </td>
                    <td class="kalla" data-testid="tackning">
                      <template v-if="tackning(f, r.organ)?.saknas">Inga åtgärder anges</template>
                      <template v-else-if="tackning(f, r.organ)?.mnkr != null">åtgärder för {{ fr(tackning(f, r.organ)!.mnkr!) }} mnkr</template>
                    </td>
                  </tr>
                  <tr v-for="(a, i) in r.atgarder ?? []" :key="`${r.organ}-${i}`" class="atgard" data-testid="atgard">
                    <td colspan="2">{{ a.text }}</td>
                    <td class="num">
                      <template v-if="a.mnkr !== undefined">{{ fr(a.mnkr) }}</template>
                      <a v-if="sidlank(f, a.sida)" :href="sidlank(f, a.sida)!" target="_blank" rel="noopener" class="sida">s. {{ a.sida }}</a>
                    </td>
                  </tr>
                </template>
              </tbody>
            </table>
            <p v-else><strong>Ramar:</strong> <span class="saknas">anges inte</span></p>
            <p data-testid="behandling">
              <strong>Behandling:</strong>
              <template v-if="f.behandling">
                <RouterLink v-if="f.behandling.sammantrade_id" :to="`/politik/sammantraden/${f.behandling.sammantrade_id}/paragraf/${f.behandling.paragraf}`">
                  {{ f.behandling.organ }} {{ f.behandling.datum }} § {{ f.behandling.paragraf }}<template v-if="f.behandling.rubrik">, {{ f.behandling.rubrik }}</template>
                </RouterLink>
                <template v-else>{{ f.behandling.organ }} {{ f.behandling.datum }} § {{ f.behandling.paragraf }} <span class="saknas">(finns inte i plattformen)</span></template>
                <template v-if="f.behandling.yrkanden.length"> · yrkande: {{ f.behandling.yrkanden[0].text }}</template>
              </template>
              <span v-else class="saknas"> anges inte</span>
            </p>
            <div v-if="f.summering" class="summering" data-testid="summering">
              <p><strong>Summering</strong> <span class="analysetikett">Analys</span></p>
              <dl>
                <template v-for="q in f.summering" :key="q.id">
                  <dt>{{ q.fraga }}</dt>
                  <dd>
                    <span v-if="q.anges_inte" class="saknas">Förslaget tar inte upp frågan</span>
                    <template v-else>
                      {{ q.text }}
                      <template v-for="sd in q.sidor ?? []" :key="sd"><a :href="sidlank(f, sd)!" target="_blank" rel="noopener" class="sida">s. {{ sd }}</a></template>
                    </template>
                  </dd>
                </template>
              </dl>
            </div>
            <p v-else><strong>Summering:</strong> <span class="saknas">saknas</span></p>
          </div>

          <div class="knappar">
            <button v-if="arRedaktor && oppen !== f.id" type="button" @click="oppna(f)">Rätta</button>
            <button v-if="arUtgivare && f.status === 'utkast'" type="button" :disabled="egen(f)" :title="egen(f) ? 'Du har läst in eller ändrat förslaget' : ''" data-testid="granska" @click="granska(f)">Granska</button>
            <button v-if="arUtgivare && f.status === 'granskad'" type="button" :disabled="egen(f)" data-testid="publicera" @click="publicera(f)">Publicera</button>
            <span v-if="meddelande[`f${f.id}`]" class="meddelande" role="status">{{ meddelande[`f${f.id}`] }}</span>
          </div>

          <form v-if="oppen === f.id && form" class="formular" @submit.prevent="spara(f)">
            <div class="falt">
              <label>Titel <input v-model="form.titel" /></label>
              <label>Partier <input v-model="form.partier" placeholder="S, MP, KD" /></label>
              <label class="kryss"><input v-model="form.antagen" type="checkbox" /> Antagen budget</label>
            </div>
            <div class="falt">
              <label>Skattesatsens förändring, öre <input v-model="form.skatt.ore" inputmode="numeric" placeholder="0" /></label>
              <label>Sida <input v-model="form.skatt.sida" inputmode="numeric" class="kort-falt" /></label>
              <label>Budgeterat resultat, % av skatter och bidrag <input v-model="form.resultat.procent" inputmode="decimal" /></label>
              <label>Sida <input v-model="form.resultat.sida" inputmode="numeric" class="kort-falt" /></label>
            </div>

            <table class="redigera">
              <caption>
                Ramar per nämnd {{ f.budgetar }}. Ange mnkr, eller lämna tomt och ange förändringen mot planförutsättningarna.
                Åtgärderna skrivs nära originalets text, med beloppet om förslaget anger det.
              </caption>
              <thead><tr><th>Nämnd</th><th>Mnkr</th><th>Förändring, mnkr</th><th>Sida</th><th /></tr></thead>
              <tbody>
                <template v-for="(r, i) in form.ramar" :key="i">
                  <tr :data-ram="r.organ">
                    <td><input v-model="r.organ" /></td>
                    <td><input v-model="r.mnkr" inputmode="decimal" /></td>
                    <td><input v-model="r.forandring" inputmode="decimal" :disabled="!!r.mnkr.trim()" /></td>
                    <td><input v-model="r.sida" class="kort-falt" /></td>
                    <td>
                      <button type="button" @click="form.ramar.splice(i, 1)">Ta bort</button>
                      <button type="button" data-testid="lagg-till-atgard" @click="r.atgarder.push({ text: '', mnkr: '', sida: '' })">Lägg till åtgärd</button>
                    </td>
                  </tr>
                  <tr v-for="(a, k) in r.atgarder" :key="`${i}-${k}`" class="atgard" data-testid="atgardsfalt" :data-ram-atgard="r.organ">
                    <td><textarea v-model="a.text" rows="2" aria-label="Åtgärd" placeholder="Åtgärd, nära originalets text" /></td>
                    <td><input v-model="a.mnkr" inputmode="decimal" aria-label="Åtgärdens belopp, mnkr" placeholder="mnkr" /></td>
                    <td />
                    <td><input v-model="a.sida" class="kort-falt" aria-label="Åtgärdens sida" /></td>
                    <td><button type="button" @click="r.atgarder.splice(k, 1)">Ta bort åtgärd</button></td>
                  </tr>
                </template>
              </tbody>
            </table>
            <button type="button" @click="form.ramar.push({ organ: '', mnkr: '', forandring: '', sida: '', atgarder: [] })">Lägg till ram</button>

            <fieldset class="grupp">
              <legend>Behandling där förslaget ställdes</legend>
              <div class="falt">
                <label>Organ <input v-model="form.behandling.organ" class="kort-falt" /></label>
                <label>Datum <input v-model="form.behandling.datum" placeholder="ÅÅÅÅ-MM-DD" data-testid="behandling-datum" /></label>
                <label>Paragraf <input v-model="form.behandling.paragraf" inputmode="numeric" class="kort-falt" data-testid="behandling-paragraf" /></label>
              </div>
            </fieldset>

            <fieldset class="grupp analysfalt">
              <legend>Summering <span class="analysetikett">Analys</span></legend>
              <p class="meta">
                Samma frågor för alla förslag. Återge vad förslaget säger, nära texten och utan värdering, med sidorna där
                det står. Fyll i alla frågor, eller ingen.
              </p>
              <div v-for="q in f.mall" :key="q.id" class="svar" :data-fraga="q.id">
                <label class="bred">{{ q.fraga }}
                  <textarea v-model="form.summering[q.id].text" rows="2" :disabled="form.summering[q.id].anges_inte" />
                </label>
                <div class="falt">
                  <label>Sidor <input v-model="form.summering[q.id].sidor" placeholder="1, 2" :disabled="form.summering[q.id].anges_inte" /></label>
                  <label class="kryss"><input v-model="form.summering[q.id].anges_inte" type="checkbox" /> Förslaget tar inte upp frågan</label>
                </div>
              </div>
            </fieldset>

            <label class="bred">Anmärkning <textarea v-model="form.anmarkning" rows="2" /></label>
            <div class="knappar">
              <button type="submit" class="primar" data-testid="spara">Spara</button>
              <button type="button" @click="oppen = null">Avbryt</button>
            </div>
          </form>
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
.lista {
  list-style: none;
  padding: 0;
  margin: 0;
}
.kort {
  background: var(--surface);
  border: 1px solid var(--line);
  border-radius: var(--radius);
  padding: 16px 24px;
  margin-bottom: 12px;
}
.huvud {
  display: flex;
  flex-wrap: wrap;
  gap: 8px 12px;
  align-items: baseline;
}
.partier {
  display: inline-flex;
  gap: 8px;
}
.etikett {
  font-size: 12px;
  color: var(--ink-secondary);
  border: 1px solid var(--line-strong);
  border-radius: var(--radius);
  padding: 0 6px;
}
.meta {
  font-size: 13px;
  color: var(--ink-secondary);
  margin: 6px 0 0;
}
.knappar {
  display: flex;
  gap: 8px;
  align-items: center;
  margin-top: 10px;
  flex-wrap: wrap;
}
button {
  font: inherit;
  font-size: 13px;
  padding: 4px 10px;
  border: 1px solid var(--line-strong);
  border-radius: var(--radius);
  background: var(--surface);
  color: var(--ink);
  cursor: pointer;
}
button:disabled {
  color: var(--ink-muted);
  cursor: not-allowed;
}
.primar {
  background: var(--accent);
  border-color: var(--accent);
  color: #fff;
}
.meddelande {
  font-size: 13px;
  color: var(--ink-secondary);
}
.formular {
  margin-top: 12px;
  border-top: 1px solid var(--line);
  padding-top: 12px;
  display: grid;
  gap: 10px;
  justify-items: start;
}
.falt {
  display: flex;
  gap: 12px;
  flex-wrap: wrap;
}
label {
  display: grid;
  gap: 4px;
  font-size: 13px;
  color: var(--ink-secondary);
}
.kryss {
  display: flex;
  align-items: center;
  gap: 6px;
}
.bred,
.bred textarea {
  width: 100%;
}
input,
textarea {
  font: inherit;
  font-size: 13px;
  color: var(--ink);
  background: var(--surface);
  border: 1px solid var(--line);
  border-radius: var(--radius);
  padding: 4px 6px;
}
input.kort-falt {
  width: 5em;
}
.redigera {
  border-collapse: collapse;
  font-size: 13px;
}
.redigera caption {
  text-align: left;
  font-weight: 600;
  padding: 4px 0;
}
.redigera th {
  text-align: left;
  font-weight: 600;
  color: var(--ink-secondary);
  padding: 2px 4px;
}
.redigera td {
  padding: 2px 4px;
}
.uppgifter {
  margin-top: 10px;
  font-size: 13px;
  overflow-x: auto;
}
.uppgifter p {
  margin: 4px 0;
}
.sida {
  font-size: 12px;
  margin-left: 4px;
}
.ramtabell {
  border-collapse: collapse;
  margin-top: 6px;
}
.ramtabell caption {
  text-align: left;
  font-weight: 600;
  padding: 4px 0;
}
.ramtabell th,
.ramtabell td {
  padding: 3px 10px 3px 0;
  border-bottom: 1px solid var(--line);
  text-align: left;
  font-weight: normal;
}
.ramtabell thead th {
  font-weight: 600;
  color: var(--ink-secondary);
}
.ramtabell .num {
  text-align: right;
  font-variant-numeric: tabular-nums;
  white-space: nowrap;
}
.grupp {
  border: 1px solid var(--line);
  border-radius: var(--radius);
  padding: 8px 12px;
  width: 100%;
  display: grid;
  gap: 8px;
}
.grupp legend {
  font-size: 13px;
  font-weight: 600;
  padding: 0 4px;
}
.analysfalt {
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
}
.svar {
  display: grid;
  gap: 4px;
}
.summering {
  margin-top: 8px;
  border: 1px dashed var(--line-strong);
  border-radius: var(--radius);
  padding: 4px 12px;
}
.summering dt {
  font-weight: 600;
  margin-top: 6px;
}
.summering dd {
  margin: 0;
}
.atgard td {
  color: var(--ink-secondary);
  padding-left: 16px;
}
.atgard textarea {
  width: 100%;
  min-width: 24em;
}
.sektion {
  font-size: 15px;
  margin: 0 0 8px;
}
.meta-inline {
  font-size: 13px;
  color: var(--ink-secondary);
}
.plantabeller {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(320px, 1fr));
  gap: 8px 32px;
  margin-top: 8px;
  font-size: 13px;
}
.kalla {
  font-size: 12px;
  color: var(--ink-muted);
}
.kontroll th,
.kontroll td {
  color: var(--ink-secondary);
}
[data-avviker] {
  color: var(--status-critical);
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
