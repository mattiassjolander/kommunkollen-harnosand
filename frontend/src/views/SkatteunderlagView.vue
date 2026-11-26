<script setup lang="ts">
// SKR:s skatteunderlagsprognoser för Härnösand (#61): den senaste prognosen per år i en tabell och
// summa intäkter för varje cirkulär i ett linjediagram, så att det syns hur prognosen för samma år har
// ändrats. Beloppen lagras i tkr och visas i mnkr. Varje värde har källhänvisning till cirkuläret.
// Revideringarna är små mot nivån, så en värmekarta visar ändringen mellan cirkulären och ett stapeldiagram
// visar vilka rader som drev en ändring (#161).
import { computed, inject, onMounted, ref } from 'vue'
import { EjInloggad, hamtaSkatteunderlagsprognoser, type Skatteunderlagsprognoser } from '../api'
import { datum, tal, talforandring } from '../format'
import { laddaNer } from '../analys'
import Linjediagram from '../components/Linjediagram.vue'
import Revideringskarta from '../components/Revideringskarta.vue'
import Drivkraftsdiagram from '../components/Drivkraftsdiagram.vue'
import {
  andring,
  budgetar,
  budgetjamforelse,
  cirkularAr,
  cirkularAren,
  drivkrafter,
  revideringar,
  SUMMARAD,
} from '../revideringar'

const utloggad = inject<() => void>('utloggad', () => {})
const data = ref<Skatteunderlagsprognoser | null>(null)
const laddar = ref(true)
const fel = ref<string | null>(null)

onMounted(async () => {
  try {
    data.value = await hamtaSkatteunderlagsprognoser()
    forval()
  } catch (e) {
    if (e instanceof EjInloggad) return utloggad()
    fel.value = e instanceof Error ? e.message : String(e)
  } finally {
    laddar.value = false
  }
})

const senaste = computed(() => data.value?.senaste ?? null)
const mnkr = (tkr: number) => tal(tkr / 1000, 'mnkr')
const summor = new Set(['summa_intakter', 'summa_inkl'])
const tvadecimaler = new Intl.NumberFormat('sv-SE', { minimumFractionDigits: 2, maximumFractionDigits: 2 })
const heltal = new Intl.NumberFormat('sv-SE', { maximumFractionDigits: 0 })

// Diagrammet visar summa intäkter inklusive avräkning och fastighetsavgift. För innevarande år ändras inte
// summa intäkter mellan cirkulären, eftersom de preliminära utbetalningarna är fastställda. Ändringen
// hamnar i slutavräkningen, som bara den här raden räknar in. Samma rad jämförs med planförutsättningarna (#62).
const DIAGRAMRAD = 'summa_inkl'

const serier = computed(() =>
  (data.value?.prognoser ?? []).map((p) => ({
    namn: `Cirkulär ${p.cirkular} (${datum(p.publicerad)})`,
    punkter: p.ar.map((a) => ({ ar: a, varde: (p.rader.find((r) => r.id === DIAGRAMRAD)?.tkr[String(a)] ?? 0) / 1000 })),
  })),
)

// Tabellvy för diagrammet: summa intäkter inklusive avräkning per cirkulär och år.
const allaAr = computed(() => [...new Set((data.value?.prognoser ?? []).flatMap((p) => p.ar))].sort((a, b) => a - b))
const summa = (cirkular: string, a: number) => {
  const p = data.value?.prognoser.find((x) => x.cirkular === cirkular)
  const v = p?.rader.find((r) => r.id === DIAGRAMRAD)?.tkr[String(a)]
  return v === undefined ? null : v
}
function exportera() {
  const rader = ['Cirkulär;Publicerad;Rad;År;Tkr;Källa']
  for (const p of data.value?.prognoser ?? []) {
    for (const r of p.rader) {
      for (const a of p.ar) rader.push([p.cirkular, p.publicerad, r.etikett, a, r.tkr[String(a)], p.url].join(';'))
    }
  }
  laddaNer('skatteunderlagsprognoser-2280.csv', rader.join('\n'))
}

// Värmekartan (B): cirkulären från ett år i taget, det senaste året förvalt.
const prognoser = computed(() => data.value?.prognoser ?? [])
const karta = ref(0)
const kartaAren = computed(() => cirkularAren(prognoser.value).filter((a) => revideringar(prognoser.value, a).length))
const kartrader = computed(() => revideringar(prognoser.value, karta.value))
function exporteraRevideringar() {
  const rader = ['Från cirkulär;Till cirkulär;Publicerad;Rad;År;Ändring tkr;Ändring procent;Källa']
  for (const r of kartrader.value) {
    for (const a of new Set([...r.fran.ar, ...r.till.ar])) {
      const c = andring(r.fran, r.till, SUMMARAD, a)
      if (!c) continue
      const pct = c.procent === null ? '' : c.procent.toFixed(4)
      rader.push([r.fran.cirkular, r.till.cirkular, r.till.publicerad, SUMMARAD, a, c.tkr.toFixed(3), pct, r.till.url].join(';'))
    }
  }
  laddaNer(`skatteunderlagsprognos-revideringar-${karta.value}.csv`, rader.join('\n'))
}

// Raden om budgeten: budgetåret, från årets första cirkulär till det senaste.
const manad = new Intl.DateTimeFormat('sv-SE', { month: 'long', timeZone: 'Europe/Stockholm' })
const budget = computed(() => {
  const j = budgetjamforelse(prognoser.value)
  if (!j) return null
  const ar = budgetar()
  if (j.fran === j.till) {
    return `Bara ett cirkulär (${j.till.cirkular}) har kommit i år, så prognosen för ${ar} har inte reviderats än.`
  }
  const c = andring(j.fran, j.till, SUMMARAD, ar)
  if (!c) return `Cirkulär ${j.fran.cirkular} och ${j.till.cirkular} har inte båda en prognos för ${ar}.`
  const mnkr = Math.round(c.tkr / 100) / 10 || 0
  const hur = mnkr > 0 ? `har höjts med ${tal(mnkr, 'mnkr')}` : mnkr < 0 ? `har sänkts med ${tal(-mnkr, 'mnkr')}` : 'är oförändrad'
  return `Prognosen för ${ar} ${hur} sedan ${manad.format(new Date(j.fran.publicerad))} (${j.fran.cirkular} → ${j.till.cirkular}).`
})

// Drivkrafterna (D): budgetåret och de två senaste cirkulären är förvalda.
const dAr = ref(0)
const dFran = ref('')
const dTill = ref('')
const allaPrognosAr = computed(() => [...new Set(prognoser.value.flatMap((p) => p.ar))].sort((a, b) => a - b))
function forval() {
  const p = prognoser.value
  const sista = p.at(-1)
  if (!sista) return
  karta.value = kartaAren.value.at(-1) ?? cirkularAr(sista)
  dTill.value = sista.cirkular
  dFran.value = (p.at(-2) ?? sista).cirkular
  const b = budgetar()
  dAr.value = allaPrognosAr.value.includes(b) ? b : sista.ar[0]
}
const prognos = (cirkular: string) => prognoser.value.find((p) => p.cirkular === cirkular) ?? null
const dPar = computed(() => {
  const fran = prognos(dFran.value)
  const till = prognos(dTill.value)
  return fran && till ? { fran, till } : null
})
const dSumma = computed(() => (dPar.value ? andring(dPar.value.fran, dPar.value.till, SUMMARAD, dAr.value) : null))
const dRader = computed(() => (dPar.value && dSumma.value ? drivkrafter(dPar.value.fran, dPar.value.till, dAr.value) : []))
const valdRad = computed(() => kartrader.value.findIndex((r) => r.fran.cirkular === dFran.value && r.till.cirkular === dTill.value))
const drivkraftsrubrik = ref<HTMLElement | null>(null)
function valjRuta(i: number, a: number) {
  const r = kartrader.value[i]
  dFran.value = r.fran.cirkular
  dTill.value = r.till.cirkular
  dAr.value = a
  drivkraftsrubrik.value?.scrollIntoView({ behavior: 'smooth', block: 'nearest' })
}
const mnkrAndring = (tkr: number) => talforandring(Math.round(tkr / 100) / 10 || 0, 'mnkr')
</script>

<template>
  <header class="vyhuvud">
    <h1>Skatteunderlagsprognos</h1>
    <p class="ingress">
      SKR:s skatteunderlagsprognos för Härnösand: skatteintäkter och generella bidrag och utjämning per år. SKR
      publicerar prognosen fem gånger per år med ett cirkulär, och budgetarbetet utgår från den. Varje cirkulär
      sparas, så att det syns hur prognosen har ändrats.
    </p>
  </header>

  <p v-if="laddar">Hämtar prognoser…</p>
  <p v-else-if="fel" class="fel" role="alert">Kunde inte hämta prognoserna: {{ fel }}</p>
  <p v-else-if="!senaste" class="saknas" data-testid="inga-prognoser">
    Uppgift saknas. Ingen skatteunderlagsprognos har samlats in än.
  </p>

  <template v-else>
    <section v-if="kartaAren.length" class="kort" aria-labelledby="revidering-rubrik" data-testid="revideringar">
      <div class="rubrikrad">
        <h2 id="revidering-rubrik">Så har prognosen ändrats mellan cirkulären</h2>
        <button type="button" data-testid="exportera-revideringar" @click="exporteraRevideringar">Ladda ner CSV</button>
      </div>
      <p class="forklaring">
        Ändringen av summa intäkter inklusive avräkning och fastighetsavgift mot föregående cirkulär, i mnkr. En rad per
        cirkulär och en kolumn per prognosår. Årets första cirkulär jämförs med det sista från året före.
      </p>
      <div v-if="kartaAren.length > 1" class="val">
        <label for="karta-ar">Cirkulär från</label>
        <select id="karta-ar" v-model.number="karta" data-testid="karta-ar">
          <option v-for="a in kartaAren" :key="a" :value="a">{{ a }}</option>
        </select>
      </div>
      <Revideringskarta :revideringar="kartrader" :vald-rad="valdRad" :valt-ar="dAr" @valj="valjRuta" />
      <p v-if="budget" class="budgetrad" data-testid="budgetrad">{{ budget }}</p>
      <p class="kallrad">Källa: SKR, prognosunderlag till varje cirkulär, omräknat för kommunkod 2280.</p>
    </section>

    <section v-if="prognoser.length > 1" class="kort" aria-labelledby="drivkraft-rubrik" data-testid="drivkrafter">
      <h2 id="drivkraft-rubrik" ref="drivkraftsrubrik">Vad som drev ändringen</h2>
      <p class="forklaring">
        Ändringen per rad i prognosunderlaget mellan två cirkulär för ett år, i mnkr. Rader som inte ändrades visas inte.
      </p>
      <div class="val">
        <label for="drivkraft-ar">År</label>
        <select id="drivkraft-ar" v-model.number="dAr" data-testid="drivkraft-ar">
          <option v-for="a in allaPrognosAr" :key="a" :value="a">{{ a }}</option>
        </select>
        <label for="drivkraft-fran">Från cirkulär</label>
        <select id="drivkraft-fran" v-model="dFran" data-testid="drivkraft-fran">
          <option v-for="p in prognoser" :key="p.cirkular" :value="p.cirkular">{{ p.cirkular }}</option>
        </select>
        <label for="drivkraft-till">Till cirkulär</label>
        <select id="drivkraft-till" v-model="dTill" data-testid="drivkraft-till">
          <option v-for="p in prognoser" :key="p.cirkular" :value="p.cirkular">{{ p.cirkular }}</option>
        </select>
      </div>
      <p v-if="!dPar || !dSumma" class="saknas" data-testid="drivkraft-saknas">
        Cirkulär {{ dFran }} och {{ dTill }} har inte båda en prognos för {{ dAr }}.
      </p>
      <template v-else>
        <Drivkraftsdiagram
          v-if="dRader.length"
          :rader="dRader"
          :rubrik="`Ändring per rad i prognosunderlaget för ${dAr} från cirkulär ${dFran} till ${dTill}, mnkr`"
          :kalla="`SKR, cirkulär ${dFran} och ${dTill}`"
        />
        <p v-else class="saknas" data-testid="inga-drivkrafter">Ingen rad i prognosunderlaget för {{ dAr }} ändrades.</p>
        <p class="summarad" data-testid="drivkraftssumma">
          Summa intäkter inklusive avräkning och fastighetsavgift {{ dAr }}:
          <strong class="tal">{{ mnkrAndring(dSumma.tkr) }}</strong>
        </p>
      </template>
      <p class="kallrad">
        Källa: SKR, prognosunderlag till cirkulär
        <a :href="dPar?.fran.url" rel="noopener" target="_blank">{{ dFran }}</a> och
        <a :href="dPar?.till.url" rel="noopener" target="_blank">{{ dTill }}</a>.
      </p>
    </section>

    <section class="kort" aria-labelledby="senaste-rubrik" data-testid="senaste-prognos">
      <h2 id="senaste-rubrik">Senaste prognosen, cirkulär {{ senaste.cirkular }}</h2>
      <p class="forklaring">
        Publicerad {{ datum(senaste.publicerad) }}. Belopp i mnkr. Prognosen räknar med skattesatsen
        {{ tvadecimaler.format(senaste.skattesats) }} % för alla år.
      </p>
      <div class="rulla">
        <table class="tabell" data-testid="prognostabell">
          <thead>
            <tr>
              <th scope="col">Mnkr</th>
              <th v-for="a in senaste.ar" :key="a" scope="col" class="num">{{ a }}</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="r in senaste.rader" :key="r.id" :data-rad="r.id" :class="{ summa: summor.has(r.id) }">
              <th scope="row">{{ r.etikett }}</th>
              <td v-for="a in senaste.ar" :key="a" class="num">{{ mnkr(r.tkr[String(a)] ?? 0) }}</td>
            </tr>
            <tr data-rad="invanare">
              <th scope="row">Antal invånare enligt riksprognosen</th>
              <td v-for="a in senaste.ar" :key="a" class="num">{{ heltal.format(senaste.invanare[String(a)]) }}</td>
            </tr>
          </tbody>
        </table>
      </div>
      <p class="kallrad">
        Källa: SKR, prognosunderlag till cirkulär {{ senaste.cirkular }},
        <a :href="senaste.url" rel="noopener" target="_blank">{{ senaste.filnamn }}</a>, omräknat för kommunkod 2280.
      </p>
    </section>

    <section class="kort" aria-labelledby="andring-rubrik" data-testid="prognosdiagram">
      <div class="rubrikrad">
        <h2 id="andring-rubrik">Summa intäkter inklusive avräkning per cirkulär</h2>
        <button type="button" data-testid="exportera" @click="exportera">Ladda ner CSV</button>
      </div>
      <p class="forklaring">
        Skatteintäkter och generella bidrag och utjämning, inklusive slutavräkningar och fastighetsavgift. En linje
        per cirkulär visar hur prognosen för samma år har ändrats. För innevarande år är utbetalningarna redan
        fastställda, så en ändrad prognos syns i slutavräkningen och kommer med här.
      </p>
      <Linjediagram
        :serier="serier"
        enhet="mnkr"
        kalla="SKR, skatteunderlagsprognoser"
        etikett="Summa intäkter inklusive avräkning och fastighetsavgift per år enligt varje cirkulär från SKR, i mnkr"
      />
      <details class="tabellvy">
        <summary>Visa som tabell</summary>
        <div class="rulla">
          <table class="tabell" data-testid="cirkulartabell">
            <thead>
              <tr>
                <th scope="col">Cirkulär</th>
                <th v-for="a in allaAr" :key="a" scope="col" class="num">{{ a }}</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="p in data!.prognoser" :key="p.cirkular" :data-cirkular="p.cirkular">
                <th scope="row"><a :href="p.url" rel="noopener" target="_blank">{{ p.cirkular }}</a> ({{ datum(p.publicerad) }})</th>
                <td v-for="a in allaAr" :key="a" class="num">{{ summa(p.cirkular, a) === null ? '–' : mnkr(summa(p.cirkular, a)!) }}</td>
              </tr>
            </tbody>
          </table>
        </div>
      </details>
      <p class="kallrad">Källa: SKR, skatteunderlagsprognoser. Äldre cirkulär än 2026 finns inte att hämta.</p>
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
  padding: 6px 8px;
  border-bottom: 1px solid var(--line);
}
.tabell tbody th {
  font-weight: 400;
}
.tabell .num {
  text-align: right;
  font-variant-numeric: tabular-nums;
  white-space: nowrap;
}
.summa th,
.summa td {
  font-weight: 600;
  border-top: 1px solid var(--line-strong);
}
.budgetrad {
  font-size: 15px;
  margin: 12px 0 0;
  max-width: 70ch;
}
.val {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 8px 12px;
  margin: 0 0 12px;
  font-size: 13px;
}
.val select {
  font: inherit;
  padding: 4px 8px;
  border: 1px solid var(--line-strong);
  border-radius: var(--radius);
  background: var(--surface);
  color: var(--ink);
}
.summarad {
  font-size: 13px;
  margin: 12px 0 0;
  padding-top: 8px;
  border-top: 1px solid var(--line-strong);
}
.tal {
  font-variant-numeric: tabular-nums;
}
.tabellvy {
  margin-top: 12px;
  font-size: 13px;
}
.kallrad {
  font-size: 12px;
  color: var(--ink-muted);
  margin: 8px 0 0;
}
button {
  white-space: nowrap;
  font: inherit;
  font-size: 13px;
  padding: 4px 10px;
  border: 1px solid var(--line-strong);
  border-radius: var(--radius);
  background: var(--surface);
  color: var(--ink);
  cursor: pointer;
}
.saknas {
  color: var(--ink-muted);
}
.fel {
  color: var(--status-critical);
}
a {
  color: var(--accent);
}
</style>
