<script setup lang="ts">
// SKR:s skatteunderlagsprognoser för Härnösand (#61): den senaste prognosen per år i en tabell och
// summa intäkter för varje cirkulär i ett linjediagram, så att det syns hur prognosen för samma år har
// ändrats. Beloppen lagras i tkr och visas i mnkr. Varje värde har källhänvisning till cirkuläret.
import { computed, inject, onMounted, ref } from 'vue'
import { EjInloggad, hamtaSkatteunderlagsprognoser, type Skatteunderlagsprognoser } from '../api'
import { datum, tal } from '../format'
import { laddaNer } from '../analys'
import EkonomiFlikar from '../components/EkonomiFlikar.vue'
import Linjediagram from '../components/Linjediagram.vue'

const utloggad = inject<() => void>('utloggad', () => {})
const data = ref<Skatteunderlagsprognoser | null>(null)
const laddar = ref(true)
const fel = ref<string | null>(null)

onMounted(async () => {
  try {
    data.value = await hamtaSkatteunderlagsprognoser()
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

const serier = computed(() =>
  (data.value?.prognoser ?? []).map((p) => ({
    namn: `Cirkulär ${p.cirkular} (${datum(p.publicerad)})`,
    punkter: p.ar.map((a) => ({ ar: a, varde: (p.rader.find((r) => r.id === 'summa_intakter')?.tkr[String(a)] ?? 0) / 1000 })),
  })),
)

// Tabellvy och CSV för diagrammet: summa intäkter per cirkulär och år.
const allaAr = computed(() => [...new Set((data.value?.prognoser ?? []).flatMap((p) => p.ar))].sort((a, b) => a - b))
const summa = (cirkular: string, a: number) => {
  const p = data.value?.prognoser.find((x) => x.cirkular === cirkular)
  const v = p?.rader.find((r) => r.id === 'summa_intakter')?.tkr[String(a)]
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
</script>

<template>
  <header class="vyhuvud">
    <h1>Ekonomi</h1>
    <p class="ingress">
      SKR:s skatteunderlagsprognos för Härnösand: skatteintäkter och generella bidrag och utjämning per år. SKR
      publicerar prognosen fem gånger per år med ett cirkulär, och budgetarbetet utgår från den. Varje cirkulär
      sparas, så att det syns hur prognosen har ändrats.
    </p>
  </header>
  <EkonomiFlikar />

  <p v-if="laddar">Hämtar prognoser…</p>
  <p v-else-if="fel" class="fel" role="alert">Kunde inte hämta prognoserna: {{ fel }}</p>
  <p v-else-if="!senaste" class="saknas" data-testid="inga-prognoser">
    Uppgift saknas. Ingen skatteunderlagsprognos har samlats in än.
  </p>

  <template v-else>
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
        <h2 id="andring-rubrik">Summa intäkter per cirkulär</h2>
        <button type="button" data-testid="exportera" @click="exportera">Ladda ner CSV</button>
      </div>
      <p class="forklaring">
        Skatteintäkter och generella bidrag och utjämning, före slutavräkningar och fastighetsavgift. En linje per
        cirkulär visar hur prognosen för samma år har ändrats.
      </p>
      <Linjediagram
        :serier="serier"
        enhet="mnkr"
        kalla="SKR, skatteunderlagsprognoser"
        etikett="Summa intäkter per år enligt varje cirkulär från SKR, i mnkr"
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
