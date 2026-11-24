<script setup lang="ts">
// En förra version av ett budgetförslag eller av planförutsättningarna (#76). En publicerad uppgift ändras genom
// en ny version, som läsaren ser märkt "Ändrad efter publicering". Härifrån kan läsaren se vad som stod innan,
// och gå vidare till versionen före den om även den var ändrad.
import { computed, inject, ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import {
  EjInloggad,
  Saknas,
  hamtaTidigareForslag,
  hamtaTidigarePlan,
  type Budgetforslag,
  type Budgetstatus,
  type Planforutsattningar,
  type Plantabell,
} from '../../api'
import { datum, tal } from '../../format'
import Partimarkering from '../../components/Partimarkering.vue'

const route = useRoute()
const utloggad = inject<() => void>('utloggad', () => {})
const slag = computed(() => (route.params.slag === 'planforutsattningar' ? 'planforutsattningar' : 'forslag'))
const forslag = ref<(Budgetforslag & { status: Budgetstatus }) | null>(null)
const plan = ref<Planforutsattningar | null>(null)
const fel = ref<string | null>(null)
const laddar = ref(true)

async function ladda() {
  laddar.value = true
  fel.value = null
  forslag.value = null
  plan.value = null
  const id = Number(route.params.id)
  try {
    if (slag.value === 'forslag') forslag.value = await hamtaTidigareForslag(id)
    else plan.value = await hamtaTidigarePlan(id)
  } catch (e) {
    if (e instanceof EjInloggad) return utloggad()
    fel.value = e instanceof Saknas ? 'Det finns ingen förra version med den adressen.' : e instanceof Error ? e.message : String(e)
  } finally {
    laddar.value = false
  }
}
watch(() => [route.params.slag, route.params.id], ladda, { immediate: true })

const version = computed(() => forslag.value ?? plan.value)
const budgetar = computed(() => version.value?.budgetar ?? null)
const tidigareLank = (id: number) => `/politik/budget/tidigare/${slag.value}/${id}`
const tvadecimaler = new Intl.NumberFormat('sv-SE', { minimumFractionDigits: 2, maximumFractionDigits: 2 })
const sidlank = (f: Budgetforslag, s?: number) => (s ? `${f.original}#page=${s}` : null)

const TABELLER: { nyckel: Plantabell; rubrik: string }[] = [
  { nyckel: 'resultatbudget', rubrik: 'Resultatbudget' },
  { nyckel: 'namnder', rubrik: 'Ramar per nämnd' },
  { nyckel: 'investeringar', rubrik: 'Investeringsbudget per nämnd' },
  { nyckel: 'balansbudget', rubrik: 'Balansbudget' },
  { nyckel: 'kassaflode', rubrik: 'Förenklad kassaflödesanalys' },
]
</script>

<template>
  <header class="vyhuvud">
    <h1>Förra versionen</h1>
  </header>

  <p v-if="fel" class="fel" role="alert">{{ fel }}</p>
  <p v-else-if="laddar">Hämtar den förra versionen…</p>
  <section v-else-if="version" class="kort" aria-labelledby="tidigare-rubrik" data-testid="tidigare-version">
    <h2 id="tidigare-rubrik">
      <template v-if="forslag">{{ forslag.titel }} {{ forslag.budgetar }}</template>
      <template v-else>Planförutsättningar {{ plan!.budgetar }}</template>
      – förra versionen
    </h2>
    <p class="notis" data-testid="tidigare-notis">
      Publicerad {{ datum(version.publicerad) }}.
      <template v-if="(forslag?.status ?? '') === 'aterkallad'">Den drogs tillbaka för rättning och har ersatts av en rättad version.</template>
      <template v-else>Den har ersatts av en rättad version.</template>
      <RouterLink :to="`/politik/budget?ar=${budgetar}`">Till den gällande versionen</RouterLink>
    </p>
    <p v-if="version.andring" class="forklaring" data-testid="tidigare-andring">
      Även den här versionen ändrades efter publicering: {{ version.andring.motivering }}
      <RouterLink :to="tidigareLank(version.andring.tidigare)">Versionen före</RouterLink>
    </p>

    <template v-if="forslag">
      <p class="partier"><Partimarkering v-for="p in forslag.partier" :key="p" :parti="p" /></p>
      <dl class="uppgifter">
        <dt>Skattesats</dt>
        <dd>
          <template v-if="forslag.berakning?.skattesats.procent != null">{{ tvadecimaler.format(forslag.berakning.skattesats.procent) }} %</template>
          <template v-else-if="forslag.uppgifter.skattesats.procent !== undefined">{{ tvadecimaler.format(forslag.uppgifter.skattesats.procent) }} %</template>
          <template v-else-if="forslag.uppgifter.skattesats.ore">{{ forslag.uppgifter.skattesats.ore }} öre</template>
          <template v-else>oförändrad</template>
        </dd>
        <dt>Budgeterat resultat</dt>
        <dd data-testid="tidigare-resultat">
          <template v-if="forslag.uppgifter.resultat">{{ tal(forslag.uppgifter.resultat.procent, '%') }} av skatter och bidrag</template>
          <template v-else>Anges inte</template>
        </dd>
      </dl>
      <table class="tabell" data-testid="tidigare-ramar">
        <caption>Ramar per nämnd {{ forslag.budgetar }}</caption>
        <tbody>
          <tr v-for="r in forslag.uppgifter.ramar" :key="r.organ">
            <th scope="row">{{ r.organ }}</th>
            <td class="num">
              <a v-if="sidlank(forslag, r.sida)" :href="sidlank(forslag, r.sida)!" target="_blank" rel="noopener">{{ tal(r.mnkr, 'mnkr') }}</a>
              <template v-else>{{ tal(r.mnkr, 'mnkr') }}</template>
            </td>
          </tr>
        </tbody>
      </table>
      <p class="kallrad"><a :href="forslag.original" target="_blank" rel="noopener">Originalet</a></p>
    </template>

    <template v-else-if="plan">
      <p>Skattesats {{ tvadecimaler.format(plan.skattesats.procent) }} %</p>
      <div class="plantabeller">
        <table v-for="t in TABELLER" :key="t.nyckel" class="tabell" :data-tabell="t.nyckel">
          <caption>{{ t.rubrik }}, mnkr</caption>
          <tbody>
            <tr v-for="x in plan.tabeller[t.nyckel]" :key="x.post">
              <th scope="row">{{ x.post }}</th>
              <td class="num">{{ tal(x.mnkr, 'mnkr') }}</td>
              <td class="kalla">{{ x.kalla }}</td>
            </tr>
          </tbody>
        </table>
      </div>
    </template>
  </section>
</template>

<style scoped>
.vyhuvud {
  margin-bottom: 24px;
}
.kort {
  background: var(--surface);
  border: 1px solid var(--line);
  border-radius: var(--radius);
  padding: 16px 24px;
}
h2 {
  font-size: 18px;
  margin: 0 0 12px;
}
.notis {
  font-size: 13px;
  max-width: 70ch;
  margin: 0 0 12px;
  padding: 6px 10px;
  border: 1px solid var(--line-strong);
  border-radius: var(--radius);
}
.forklaring,
.kallrad {
  font-size: 13px;
  color: var(--ink-secondary);
  max-width: 70ch;
}
.partier {
  display: flex;
  gap: 8px;
}
.uppgifter {
  display: grid;
  grid-template-columns: max-content 1fr;
  gap: 4px 16px;
  font-size: 14px;
}
.uppgifter dt {
  color: var(--ink-secondary);
}
.uppgifter dd {
  margin: 0;
}
.plantabeller {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
  gap: 8px 32px;
}
.tabell {
  border-collapse: collapse;
  font-size: 13px;
  margin-top: 8px;
}
.tabell caption {
  text-align: left;
  font-weight: 600;
  padding: 4px 0;
}
.tabell th,
.tabell td {
  padding: 3px 10px 3px 0;
  border-bottom: 1px solid var(--line);
  text-align: left;
  font-weight: normal;
}
.tabell .num {
  text-align: right;
  font-variant-numeric: tabular-nums;
  white-space: nowrap;
}
.kalla {
  font-size: 12px;
  color: var(--ink-muted);
}
.fel {
  color: var(--status-critical);
}
a {
  color: var(--accent);
}
</style>
