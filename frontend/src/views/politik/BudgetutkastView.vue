<script setup lang="ts">
// Budgetförslag som utkast (#48): redaktören rättar siffrorna mot originalet, och en utgivare som
// inte läst in eller ändrat förslaget granskar och publicerar det (kravspec 18).
import { computed, inject, onMounted, reactive, ref, type Ref } from 'vue'
import {
  EjInloggad,
  andraBudgetforslag,
  granskaBudgetforslag,
  hamtaBudgetutkast,
  publiceraBudgetforslag,
  type Budgetuppgifter,
  type Budgetutkast,
  type Jag,
} from '../../api'
import { datumTid } from '../../format'
import Partimarkering from '../../components/Partimarkering.vue'
import PolitikFlikar from '../../components/PolitikFlikar.vue'

const utloggad = inject<() => void>('utloggad', () => {})
const jag = inject<Ref<Jag | null>>('jag', ref(null))
const arRedaktor = computed(() => jag.value?.roller.includes('redaktor') ?? false)
const arUtgivare = computed(() => jag.value?.roller.includes('utgivare') ?? false)

const lista = ref<Budgetutkast[]>([])
const laddar = ref(true)
const fel = ref<string | null>(null)
const oppen = ref<number | null>(null)
const meddelande = reactive<Record<number, string>>({})

interface Formular {
  titel: string
  partier: string
  antagen: boolean
  anmarkning: string
  utgangslage: string
  skatt: { procent: string; forandring: string; sida: string }
  resultat: { ar: string; mnkr: string; procent: string; sida: string }[]
  ramar: { organ: string; ar: string; mnkr: string; forandring: string; sida: string }[]
}
const form = ref<Formular | null>(null)

async function ladda() {
  laddar.value = true
  fel.value = null
  try {
    const [utkast, granskade] = await Promise.all([hamtaBudgetutkast('utkast'), hamtaBudgetutkast('granskad')])
    lista.value = [...utkast, ...granskade].sort((a, b) => b.budgetar - a.budgetar || a.nyckel.localeCompare(b.nyckel))
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
    utgangslage: u.utgangslage ?? '',
    skatt: { procent: s(u.skattesats?.procent), forandring: s(u.skattesats?.forandring), sida: s(u.skattesats?.sida) },
    resultat: u.resultat.map((r) => ({ ar: s(r.ar), mnkr: s(r.mnkr), procent: s(r.procent), sida: s(r.sida) })),
    ramar: u.ramar.map((r) => ({ organ: r.organ, ar: s(r.ar), mnkr: s(r.mnkr), forandring: s(r.forandring), sida: s(r.sida) })),
  }
}

// Tal skrivs med komma eller punkt. Tomma fält skickas inte.
const tal = (v: string) => (v.trim() === '' ? undefined : Number(v.replace(/\s/g, '').replace(',', '.').replace('−', '-')))
function uppgifter(f: Formular): Budgetuppgifter {
  const harSkatt = f.skatt.procent.trim() || f.skatt.forandring.trim()
  return {
    skattesats: harSkatt ? { procent: tal(f.skatt.procent), forandring: tal(f.skatt.forandring), sida: tal(f.skatt.sida) } : null,
    resultat: f.resultat.map((r) => ({ ar: tal(r.ar)!, mnkr: tal(r.mnkr), procent: tal(r.procent), sida: tal(r.sida) })),
    ramar: f.ramar.map((r) => ({ organ: r.organ, ar: tal(r.ar)!, mnkr: tal(r.mnkr), forandring: tal(r.forandring), sida: tal(r.sida) })),
    utgangslage: f.utgangslage.trim() || null,
  }
}

async function steg(f: Budgetutkast, gor: () => Promise<Budgetutkast>, klart: string) {
  meddelande[f.id] = ''
  try {
    const ny = await gor()
    if (ny.status === 'publicerad') lista.value = lista.value.filter((x) => x.id !== f.id)
    else lista.value = lista.value.map((x) => (x.id === f.id ? ny : x))
    meddelande[f.id] = klart
    if (ny.status !== 'utkast') oppen.value = null
  } catch (e) {
    if (e instanceof EjInloggad) return utloggad()
    meddelande[f.id] = e instanceof Error ? e.message : String(e)
  }
}
const spara = (f: Budgetutkast) =>
  steg(
    f,
    () =>
      andraBudgetforslag(f.id, {
        titel: form.value!.titel,
        partier: form.value!.partier.split(/[,\s+]+/).filter(Boolean),
        antagen: form.value!.antagen,
        anmarkning: form.value!.anmarkning,
        uppgifter: uppgifter(form.value!),
      }),
    'Sparat som utkast.',
  )
const granska = (f: Budgetutkast) => steg(f, () => granskaBudgetforslag(f.id), 'Granskat.')
const publicera = (f: Budgetutkast) => steg(f, () => publiceraBudgetforslag(f.id), 'Publicerat.')
const andrat = (f: Budgetutkast) => JSON.stringify(f.uppgifter) !== JSON.stringify(f.inlast)
const egen = (f: Budgetutkast) => !!jag.value && f.redaktorer.includes(jag.value.epost)

// Granskningsvyn: siffrorna som de står i uppgifterna, utan avrundning, med sidan i originalet.
const exakt = new Intl.NumberFormat('sv-SE', { maximumFractionDigits: 3 })
const med = new Intl.NumberFormat('sv-SE', { maximumFractionDigits: 3, signDisplay: 'exceptZero' })
const nr = (v: number) => exakt.format(v)
const fr = (v: number) => (v === 0 ? '±0' : med.format(v))
const sidlank = (f: Budgetutkast, sida?: number) => (sida ? `${f.original}#page=${sida}` : null)
const aren = (f: Budgetutkast) => [...new Set(f.uppgifter.ramar.map((r) => r.ar))].sort((a, b) => a - b)
const organen = (f: Budgetutkast) => [...new Set(f.uppgifter.ramar.map((r) => r.organ))]
const ramFor = (f: Budgetutkast, organ: string, ar: number) => f.uppgifter.ramar.find((r) => r.organ === organ && r.ar === ar)
</script>

<template>
  <header class="vyhuvud">
    <h1>Politik och beslut</h1>
    <p class="ingress">
      Budgetförslag som lästs in och väntar på publicering. Kontrollera varje siffra mot sidan i originalet. En utgivare
      som inte läst in eller ändrat förslaget granskar och publicerar det.
    </p>
  </header>
  <PolitikFlikar />

  <p v-if="fel" class="fel" role="alert">{{ fel }}</p>
  <p v-else-if="laddar">Hämtar utkast…</p>
  <p v-else-if="!lista.length" class="saknas" data-testid="inga-utkast">Inga budgetförslag väntar på publicering.</p>
  <ul v-else class="lista">
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
          <template v-if="f.uppgifter.skattesats">
            <template v-if="f.uppgifter.skattesats.procent !== undefined">{{ nr(f.uppgifter.skattesats.procent) }} %</template>
            <template v-if="f.uppgifter.skattesats.forandring !== undefined">
              {{ f.uppgifter.skattesats.procent !== undefined ? ', förändring ' : '' }}{{ fr(f.uppgifter.skattesats.forandring) }} procentenheter
            </template>
            <a v-if="sidlank(f, f.uppgifter.skattesats.sida)" :href="sidlank(f, f.uppgifter.skattesats.sida)!" target="_blank" rel="noopener" class="sida">s. {{ f.uppgifter.skattesats.sida }}</a>
          </template>
          <span v-else class="saknas">anges inte</span>
          <template v-if="f.uppgifter.utgangslage"> · Förändringar räknas från {{ f.uppgifter.utgangslage }}</template>
        </p>
        <p>
          <strong>Budgeterat resultat:</strong>
          <span v-if="!f.uppgifter.resultat.length" class="saknas"> anges inte</span>
          <span v-for="(r, i) in f.uppgifter.resultat" :key="r.ar">
            {{ i ? ' · ' : ' ' }}{{ r.ar }}:
            <template v-if="r.mnkr !== undefined">{{ nr(r.mnkr) }} mnkr</template>
            <template v-if="r.procent !== undefined">{{ r.mnkr !== undefined ? ', ' : '' }}{{ nr(r.procent) }} %</template>
            <a v-if="sidlank(f, r.sida)" :href="sidlank(f, r.sida)!" target="_blank" rel="noopener" class="sida">s. {{ r.sida }}</a>
          </span>
        </p>
        <table v-if="f.uppgifter.ramar.length" class="ramtabell">
          <caption>Ramar per nämnd, mnkr (förändring inom parentes)</caption>
          <thead>
            <tr><th scope="col">Nämnd</th><th v-for="ar in aren(f)" :key="ar" scope="col" class="num">{{ ar }}</th></tr>
          </thead>
          <tbody>
            <tr v-for="o in organen(f)" :key="o">
              <th scope="row">{{ o }}</th>
              <td v-for="ar in aren(f)" :key="ar" class="num">
                <template v-if="ramFor(f, o, ar)">
                  <template v-if="ramFor(f, o, ar)!.mnkr !== undefined">{{ nr(ramFor(f, o, ar)!.mnkr!) }}</template>
                  <template v-if="ramFor(f, o, ar)!.forandring !== undefined"> ({{ fr(ramFor(f, o, ar)!.forandring!) }})</template>
                  <a v-if="sidlank(f, ramFor(f, o, ar)!.sida)" :href="sidlank(f, ramFor(f, o, ar)!.sida)!" target="_blank" rel="noopener" class="sida">s. {{ ramFor(f, o, ar)!.sida }}</a>
                </template>
                <span v-else class="saknas">–</span>
              </td>
            </tr>
          </tbody>
        </table>
        <p v-else><strong>Ramar:</strong> <span class="saknas">anges inte</span></p>
      </div>

      <div class="knappar">
        <button v-if="arRedaktor && oppen !== f.id" type="button" @click="oppna(f)">Rätta</button>
        <button v-if="arUtgivare && f.status === 'utkast'" type="button" :disabled="egen(f)" :title="egen(f) ? 'Du har läst in eller ändrat förslaget' : ''" data-testid="granska" @click="granska(f)">Granska</button>
        <button v-if="arUtgivare && f.status === 'granskad'" type="button" :disabled="egen(f)" data-testid="publicera" @click="publicera(f)">Publicera</button>
        <span v-if="meddelande[f.id]" class="meddelande" role="status">{{ meddelande[f.id] }}</span>
      </div>

      <form v-if="oppen === f.id && form" class="formular" @submit.prevent="spara(f)">
        <div class="falt">
          <label>Titel <input v-model="form.titel" /></label>
          <label>Partier <input v-model="form.partier" placeholder="S, MP, KD" /></label>
          <label class="kryss"><input v-model="form.antagen" type="checkbox" /> Antagen budget</label>
        </div>
        <div class="falt">
          <label>Skattesats, % <input v-model="form.skatt.procent" inputmode="decimal" /></label>
          <label>Förändring, procentenheter <input v-model="form.skatt.forandring" inputmode="decimal" /></label>
          <label>Sida <input v-model="form.skatt.sida" inputmode="numeric" class="kort-falt" /></label>
          <label>Förändringar räknas från <input v-model="form.utgangslage" placeholder="Planförutsättningar 2027" /></label>
        </div>

        <table class="redigera">
          <caption>Budgeterat resultat</caption>
          <thead><tr><th>År</th><th>Mnkr</th><th>% av skatter och bidrag</th><th>Sida</th><th /></tr></thead>
          <tbody>
            <tr v-for="(r, i) in form.resultat" :key="i">
              <td><input v-model="r.ar" class="kort-falt" /></td>
              <td><input v-model="r.mnkr" inputmode="decimal" /></td>
              <td><input v-model="r.procent" inputmode="decimal" /></td>
              <td><input v-model="r.sida" class="kort-falt" /></td>
              <td><button type="button" @click="form.resultat.splice(i, 1)">Ta bort</button></td>
            </tr>
          </tbody>
        </table>
        <button type="button" @click="form.resultat.push({ ar: String(f.budgetar), mnkr: '', procent: '', sida: '' })">Lägg till år</button>

        <table class="redigera">
          <caption>Ramar per nämnd</caption>
          <thead><tr><th>Nämnd</th><th>År</th><th>Mnkr</th><th>Förändring, mnkr</th><th>Sida</th><th /></tr></thead>
          <tbody>
            <tr v-for="(r, i) in form.ramar" :key="i">
              <td><input v-model="r.organ" /></td>
              <td><input v-model="r.ar" class="kort-falt" /></td>
              <td><input v-model="r.mnkr" inputmode="decimal" /></td>
              <td><input v-model="r.forandring" inputmode="decimal" /></td>
              <td><input v-model="r.sida" class="kort-falt" /></td>
              <td><button type="button" @click="form.ramar.splice(i, 1)">Ta bort</button></td>
            </tr>
          </tbody>
        </table>
        <button type="button" @click="form.ramar.push({ organ: '', ar: String(f.budgetar), mnkr: '', forandring: '', sida: '' })">Lägg till ram</button>

        <label class="bred">Anmärkning <textarea v-model="form.anmarkning" rows="2" /></label>
        <div class="knappar">
          <button type="submit" class="primar" data-testid="spara">Spara</button>
          <button type="button" @click="oppen = null">Avbryt</button>
        </div>
      </form>
    </li>
  </ul>
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
