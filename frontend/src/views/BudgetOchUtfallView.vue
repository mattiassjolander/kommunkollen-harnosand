<script setup lang="ts">
// Budget jämfört med utfall per budgetår (#83, kravspec 3.2). Antagen budget ur årsplanen, reviderad budget och
// utfall ur årsredovisningen och helårsprognos ur delårsrapporten, för årets resultat och per nämnd. Varje siffra
// länkar till sidan i dokumentet. Året står i URL:en (?ar=).
import { computed, inject, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import {
  EjInloggad,
  Saknas,
  hamtaUppfoljning,
  hamtaUppfoljningsar,
  type Budgetavvikelse,
  type Sidbelopp,
  type Uppfoljning,
} from '../api'
import { datum, tal } from '../format'
import { laddaNer, skillnad } from '../analys'
import EkonomiFlikar from '../components/EkonomiFlikar.vue'

const utloggad = inject<() => void>('utloggad', () => {})
const route = useRoute()
const router = useRouter()
const arlista = ref<number[]>([])
const data = ref<Uppfoljning | null>(null)
const aterkallad = ref(false)
const laddar = ref(true)
const fel = ref<string | null>(null)

const ar = computed<number | null>({
  get: () => (typeof route.query.ar === 'string' ? Number(route.query.ar) : (arlista.value[0] ?? null)),
  set: (v) => router.replace({ query: { ...route.query, ar: v ? String(v) : undefined } }),
})

async function ladda() {
  if (ar.value === null) return
  laddar.value = true
  fel.value = null
  data.value = null
  aterkallad.value = false
  try {
    const svar = await hamtaUppfoljning(ar.value)
    if ('aterkallad' in svar && svar.aterkallad === true) aterkallad.value = true
    else data.value = svar as Uppfoljning
  } catch (e) {
    if (e instanceof EjInloggad) return utloggad()
    if (!(e instanceof Saknas)) fel.value = e instanceof Error ? e.message : String(e)
  } finally {
    laddar.value = false
  }
}

onMounted(async () => {
  try {
    arlista.value = (await hamtaUppfoljningsar()).map((x) => x.budgetar)
  } catch (e) {
    if (e instanceof EjInloggad) return utloggad()
    fel.value = e instanceof Error ? e.message : String(e)
    laddar.value = false
    return
  }
  if (ar.value === null) laddar.value = false
  else await ladda()
})
watch(() => route.query.ar, ladda)

const ars = computed(() => data.value?.dokument.arsredovisning ?? null)
const delar = computed(() => data.value?.dokument.delarsrapport ?? null)
const res = computed(() => data.value?.berakning.resultat ?? null)
const namnder = computed(() => data.value?.berakning.namnder ?? [])
const avvikande = computed(() => namnder.value.filter((n) => n.kontroll && !n.kontroll.stammer))
const kontrollerade = computed(
  () => namnder.value.filter((n) => n.kontroll).length + (res.value?.kontroll ? 1 : 0),
)

const mnkr = (v: number | null | undefined) => (v === null || v === undefined ? '–' : tal(v, 'mnkr'))
const med = (a: Budgetavvikelse | null) => (a ? skillnad(a.mnkr, 'mnkr') : '–')
const procent = (a: Budgetavvikelse | null) => (a && a.procent !== null ? skillnad(a.procent, '').replace(/$/, ' %') : '')
const sidlank = (url: string | undefined, b: Sidbelopp | null) => (url && b?.sida ? `${url}#page=${b.sida}` : url)
const antagenLank = (b: Sidbelopp | null) =>
  data.value?.antagen ? sidlank(data.value.antagen.original, b) : undefined
const behandling = computed(() => data.value?.antagen?.behandling ?? null)

function exportera() {
  const d = data.value
  if (!d) return
  const v = (b: { mnkr: number } | null) => (b ? String(b.mnkr).replace('.', ',') : '')
  const rader = [
    'År;Post;Antagen budget (mnkr);Reviderad budget (mnkr);Prognosavvikelse delår (mnkr);Utfall (mnkr);' +
      'Avvikelse mot reviderad (mnkr);Avvikelse mot antagen (mnkr);Källa',
  ]
  const kallor = [d.antagen?.titel, ars.value?.titel, delar.value?.titel].filter(Boolean).join(', ')
  const r = d.berakning.resultat
  rader.push(
    [d.budgetar, 'Årets resultat', v(r.antagen), v(r.reviderad), v(r.prognosavvikelse), v(r.utfall),
      v(r.avvikelse_reviderad), v(r.avvikelse_antagen), kallor].join(';'),
  )
  for (const n of d.berakning.namnder) {
    rader.push(
      [d.budgetar, n.organ, v(n.antagen), v(n.reviderad), v(n.prognosavvikelse), v(n.utfall),
        v(n.avvikelse_reviderad), v(n.avvikelse_antagen), kallor].join(';'),
    )
  }
  laddaNer(`budget-och-utfall-${d.budgetar}.csv`, rader.join('\n'))
}
</script>

<template>
  <header class="vyhuvud">
    <h1>Ekonomi</h1>
    <p class="ingress">
      Budgeten som fullmäktige antog, budgeten efter ändringarna under året, helårsprognosen i delårsrapporten och
      utfallet i årsredovisningen, för årets resultat och för varje nämnd. Varje siffra länkar till sidan i
      dokumentet den står i.
    </p>
  </header>
  <EkonomiFlikar />

  <div v-if="arlista.length" class="filter">
    <label for="uppfoljning-ar">Budgetår</label>
    <select id="uppfoljning-ar" v-model.number="ar" data-testid="uppfoljning-ar">
      <option v-for="a in arlista" :key="a" :value="a">{{ a }}</option>
    </select>
  </div>

  <p v-if="laddar">Hämtar budget och utfall…</p>
  <p v-else-if="fel" class="fel" role="alert">Kunde inte hämta budget och utfall: {{ fel }}</p>
  <p v-else-if="aterkallad" class="notis" data-testid="uppfoljning-aterkallad">
    Uppgifterna för {{ ar }} är återkallade för rättning och visas igen när en rättad version har publicerats.
  </p>
  <p v-else-if="!data" class="saknas" data-testid="ingen-uppfoljning">
    Uppgift saknas. Ingen jämförelse av budget och utfall är publicerad än.
  </p>
  <template v-else>
    <p v-if="data.andring" class="notis" data-testid="andrad">
      Ändrad efter publicering: {{ data.andring.motivering }}
    </p>

    <section class="kort" aria-labelledby="resultat-rubrik" data-testid="uppfoljning-resultat">
      <h2 id="resultat-rubrik">Årets resultat {{ data.budgetar }}</h2>
      <p class="forklaring">
        Avvikelsen är resultatet minus det budgeterade resultatet. Den reviderade budgeten är budgeten vid årets slut,
        efter fullmäktiges ändringar under året.
      </p>
      <div class="rulla">
        <table class="tabell">
          <thead>
            <tr>
              <th scope="col">Uppgift</th>
              <th scope="col" class="num">Belopp</th>
              <th scope="col" class="num">Avvikelse</th>
              <th scope="col">Källa</th>
            </tr>
          </thead>
          <tbody>
            <tr data-rad="antagen">
              <th scope="row">Antagen budget</th>
              <td class="num">
                <template v-if="res?.antagen">{{ mnkr(res.antagen.mnkr) }}</template>
                <template v-else>–</template>
              </td>
              <td class="num"></td>
              <td>
                <a v-if="res?.antagen" :href="antagenLank(res.antagen)" target="_blank" rel="noopener">
                  {{ data.antagen?.titel }}<template v-if="res.antagen.sida">, s. {{ res.antagen.sida }}</template>
                </a>
                <span v-if="res?.antagen?.beraknat" class="not">
                  {{ tal(res.antagen.procent, '%') }} av skatter och bidrag, i mnkr räknat ur planförutsättningarna
                </span>
                <span v-else-if="!res?.antagen" class="not">Årsplanen anger inget resultat i mnkr.</span>
              </td>
            </tr>
            <tr data-rad="reviderad">
              <th scope="row">Reviderad budget</th>
              <td class="num">{{ mnkr(res?.reviderad?.mnkr) }}</td>
              <td class="num"></td>
              <td>
                <a v-if="res?.reviderad" :href="sidlank(ars?.url, res.reviderad)" target="_blank" rel="noopener">
                  {{ ars?.titel }}, s. {{ res.reviderad.sida }}
                </a>
              </td>
            </tr>
            <tr v-if="res?.prognos" data-rad="prognos">
              <th scope="row">Helårsprognos i delårsrapporten</th>
              <td class="num">{{ mnkr(res.prognos.mnkr) }}</td>
              <td class="num" data-testid="prognosavvikelse-resultat">
                {{ med(res.prognosavvikelse) }}
              </td>
              <td>
                <a :href="sidlank(delar?.url, res.prognos)" target="_blank" rel="noopener">
                  {{ delar?.titel }}, s. {{ res.prognos.sida }}
                </a>
                <span v-if="res.prognos_budget" class="not">
                  mot budgeterat resultat {{ mnkr(res.prognos_budget.mnkr) }} vid delåret
                </span>
              </td>
            </tr>
            <tr data-rad="utfall" class="summa">
              <th scope="row">Utfall</th>
              <td class="num">{{ mnkr(res?.utfall?.mnkr) }}</td>
              <td class="num" data-testid="avvikelse-resultat">{{ med(res?.avvikelse_reviderad ?? null) }}</td>
              <td>
                <a v-if="res?.utfall" :href="sidlank(ars?.url, res.utfall)" target="_blank" rel="noopener">
                  {{ ars?.titel }}, s. {{ res.utfall.sida }}
                </a>
                <span v-else class="not">Årsredovisningen för {{ data.budgetar }} finns inte än.</span>
                <span v-if="res?.avvikelse_antagen && res.antagen" class="not">
                  mot antagen budget: {{ med(res.avvikelse_antagen) }}
                </span>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </section>

    <section class="kort" aria-labelledby="namnder-rubrik" data-testid="uppfoljning-namnder">
      <div class="rubrikrad">
        <h2 id="namnder-rubrik">Nämnderna {{ data.budgetar }}</h2>
        <button type="button" data-testid="uppfoljning-csv" @click="exportera">CSV</button>
      </div>
      <p class="forklaring">
        Belopp är nettokostnader i mnkr. Avvikelsen är budgeten minus nettokostnaden, som i årsredovisningen: plus
        betyder att nettokostnaden blev lägre än budgeten, minus att den blev högre. Den räknas mot den reviderade
        budgeten och, på raden under, mot den antagna. Prognosen är delårsrapportens helårsprognos räknad på samma
        sätt. Procenten är av budgeten.
      </p>
      <div class="rulla">
        <table class="tabell" data-testid="namndtabell">
          <thead>
            <tr>
              <th scope="col">Nämnd</th>
              <th scope="col" class="num">Antagen budget</th>
              <th scope="col" class="num">Reviderad budget</th>
              <th v-if="delar" scope="col" class="num">Prognos (delår)</th>
              <th v-if="ars" scope="col" class="num">Utfall</th>
              <th v-if="ars" scope="col" class="num">Avvikelse</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="n in namnder" :key="n.organ" :data-organ="n.organ">
              <th scope="row">{{ n.organ }}</th>
              <td class="num">
                <a v-if="n.antagen" :href="antagenLank(n.antagen)" target="_blank" rel="noopener">{{ mnkr(n.antagen.mnkr) }}</a>
                <span v-else title="Nämnden finns inte i årsplanen">–</span>
              </td>
              <td class="num">
                <a v-if="n.reviderad" :href="sidlank(ars?.url, n.reviderad)" target="_blank" rel="noopener">{{ mnkr(n.reviderad.mnkr) }}</a>
                <template v-else>–</template>
              </td>
              <td v-if="delar" class="num" data-kolumn="prognos">
                <template v-if="n.prognosavvikelse">
                  <a :href="sidlank(delar.url, n.prognosavvikelse)" target="_blank" rel="noopener">{{ med(n.prognosavvikelse) }}</a>
                  <span class="procent">{{ procent(n.prognosavvikelse) }}</span>
                </template>
                <template v-else>–</template>
              </td>
              <td v-if="ars" class="num">
                <a v-if="n.utfall" :href="sidlank(ars.url, n.utfall)" target="_blank" rel="noopener">{{ mnkr(n.utfall.mnkr) }}</a>
                <template v-else>–</template>
              </td>
              <td v-if="ars" class="num" data-kolumn="avvikelse">
                {{ med(n.avvikelse_reviderad) }} <span class="procent">{{ procent(n.avvikelse_reviderad) }}</span>
                <span v-if="n.avvikelse_antagen" class="procent" data-kolumn="avvikelse-antagen">
                  mot antagen {{ med(n.avvikelse_antagen) }}
                </span>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
      <p v-if="data.berakning.utan_uppfoljning.length" class="forklaring" data-testid="utan-uppfoljning">
        I årsplanen men inte i uppföljningen:
        <template v-for="(u, i) in data.berakning.utan_uppfoljning" :key="u.organ">
          {{ i ? ', ' : '' }}{{ u.organ }} ({{ mnkr(u.antagen.mnkr) }})</template
        ><span>. Nämnder kan ha lagts samman eller bytt namn under året.</span>
      </p>
      <p v-if="avvikande.length" class="kontroll avviker" data-testid="uppfoljning-avviker">
        Avvikelsen som årsredovisningen anger stämmer inte med den räknade för
        <template v-for="(n, i) in avvikande" :key="n.organ">
          {{ i ? ', ' : '' }}{{ n.organ }} (anger {{ mnkr(n.kontroll!.angiven) }} på s. {{ n.kontroll!.sida }}, räknat
          {{ mnkr(n.kontroll!.raknad) }})
        </template>.
      </p>
      <p v-else-if="kontrollerade" class="kontroll" data-testid="uppfoljning-kontroll">
        Kontroll: avvikelserna som årsredovisningen anger stämmer med de räknade, inom avrundningen.
      </p>
    </section>

    <p class="kallrad" data-testid="uppfoljning-kallor">
      Källor:
      <template v-if="data.antagen">
        <a :href="data.antagen.original" target="_blank" rel="noopener">{{ data.antagen.titel }}</a>
        <template v-if="behandling">
          (antagen av {{ behandling.organ }} {{ datum(behandling.datum) }},
          <RouterLink
            v-if="behandling.hittad && behandling.sammantrade_id"
            :to="`/politik/sammantraden/${behandling.sammantrade_id}/paragraf/${behandling.paragraf}`"
            data-testid="behandling"
          >§ {{ behandling.paragraf }}</RouterLink>
          <template v-else>§ {{ behandling.paragraf }}</template>)
        </template>
        ·
        <RouterLink :to="{ path: '/politik/budget', query: { ar: data.budgetar } }">Budgetförslagen {{ data.budgetar }}</RouterLink>
        ·
      </template>
      <template v-if="ars">
        <a :href="ars.url" target="_blank" rel="noopener">{{ ars.titel }}</a> ·
      </template>
      <template v-if="delar">
        <a :href="delar.url" target="_blank" rel="noopener">{{ delar.titel }}</a> ·
      </template>
      Avlästa av Kommunkollen och granskade före publicering<template v-if="data.publicerad">, publicerade {{ datum(data.publicerad) }}</template>.
    </p>
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
  align-items: center;
  gap: 8px;
  margin-bottom: 16px;
  font-size: 14px;
}
.filter select {
  font: inherit;
  padding: 4px 8px;
  border: 1px solid var(--line-strong);
  border-radius: var(--radius);
  background: var(--surface);
  color: var(--ink);
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
  vertical-align: top;
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
}
.procent,
.not {
  display: block;
  font-size: 12px;
  font-weight: 400;
  color: var(--ink-muted);
}
.kontroll {
  font-size: 13px;
  color: var(--ink-secondary);
  margin: 12px 0 0;
}
.kontroll.avviker {
  color: var(--ink);
}
.kallrad {
  font-size: 12px;
  color: var(--ink-muted);
  margin: 8px 0 24px;
}
.kallrad a,
.tabell a {
  color: inherit;
}
.notis {
  background: var(--surface);
  border: 1px solid var(--line-strong);
  border-radius: var(--radius);
  padding: 12px 16px;
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
  color: var(--danger, var(--ink));
}
</style>
