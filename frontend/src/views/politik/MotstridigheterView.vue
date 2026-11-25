<script setup lang="ts">
// Motstridigheter i styrande dokument (#151): de publicerade, samlade för att kunna anmälas till kommunen. Motsvarar
// Att anmäla för protokollavvikelserna (#47). En redaktör sätter status och kopierar en saklig sammanställning. En
// utgivare kan återkalla. Filtren speglas i URL:en (design.md, Filter).
import { computed, inject, reactive, ref, watch, type Ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import {
  EjInloggad,
  aterkallaMotstridighet,
  hamtaMotstridigheter,
  sattMotstridighetsstatus,
  type Jag,
  type Motstridighet,
  type Motstridigheter,
  type Motstridighetsstatus,
} from '../../api'
import Motstridighetskort from '../../components/Motstridighetskort.vue'
import { tal } from '../../format'

const route = useRoute()
const router = useRouter()
const utloggad = inject<() => void>('utloggad', () => {})
const jag = inject<Ref<Jag | null>>('jag', ref(null))
const arRedaktor = computed(() => jag.value?.roller.includes('redaktor') ?? false)
const arUtgivare = computed(() => jag.value?.roller.includes('utgivare') ?? false)

function fraga(namn: string) {
  return computed<string>({
    get: () => (typeof route.query[namn] === 'string' ? (route.query[namn] as string) : ''),
    set: (v) => router.replace({ query: { ...route.query, [namn]: v || undefined } }),
  })
}
const typ = fraga('typ')
const status = fraga('status')

const a = ref<Motstridigheter | null>(null)
const laddar = ref(true)
const fel = ref<string | null>(null)

async function ladda() {
  laddar.value = true
  fel.value = null
  try {
    a.value = await hamtaMotstridigheter({ typ: typ.value, status: status.value })
  } catch (e) {
    if (e instanceof EjInloggad) return utloggad()
    fel.value = e instanceof Error ? e.message : String(e)
  } finally {
    laddar.value = false
  }
}
watch([typ, status], ladda, { immediate: true })

// Redaktörens statusformulär och utgivarens återkallelse, ett per motstridighet.
const formular = reactive<Record<number, { status: Motstridighetsstatus; datum: string; anteckning: string }>>({})
const aterkallelse = reactive<Record<number, string>>({})
const sparar = ref<number | null>(null)
const atgardsfel = reactive<Record<number, string>>({})

async function utfor(m: Motstridighet, steg: () => Promise<unknown>) {
  sparar.value = m.id
  delete atgardsfel[m.id]
  try {
    await steg()
    delete formular[m.id]
    delete aterkallelse[m.id]
    await ladda()
  } catch (e) {
    if (e instanceof EjInloggad) return utloggad()
    atgardsfel[m.id] = e instanceof Error ? e.message : String(e)
  } finally {
    sparar.value = null
  }
}
const spara = (m: Motstridighet) => {
  const f = formular[m.id]
  return utfor(m, () => sattMotstridighetsstatus(m.id, f.status, f.datum, f.anteckning))
}
const aterkalla = (m: Motstridighet) => utfor(m, () => aterkallaMotstridighet(m.id, aterkallelse[m.id]))

/** En saklig text att skicka till kommunen. */
function sammanstallning(m: Motstridighet): string {
  const rader = [`${m.typnamn}: ${m.forklaring}`, '']
  for (const c of m.citat) {
    const plats = [c.paragraf, `sidan ${c.sida}`].filter(Boolean).join(', ')
    rader.push(`${c.titel}, ${plats}: ”${c.text}”`)
  }
  if (m.uppgift) rader.push(`${m.uppgift.text} (${m.uppgift.titel}, sidan ${m.uppgift.sida})`)
  if (m.typ === 'flera_versioner') rader.push(`Dokumenten: ${m.dokument.map((d) => d.titel).join(', ')}`)
  rader.push('', 'Källa: Kommunens styrande dokument, harnosand.se', '', 'Kan dokumenten ses över, eller finns det en förklaring?')
  return rader.join('\n')
}
const kopierad = ref<number | null>(null)
async function kopiera(m: Motstridighet) {
  try {
    await navigator.clipboard.writeText(sammanstallning(m))
    kopierad.value = m.id
  } catch {
    kopierad.value = null
  }
}
</script>

<template>
  <header class="vyhuvud">
    <p class="tillbaka"><RouterLink to="/politik/styrande-dokument">‹ Styrande dokument</RouterLink></p>
    <h1>Motstridigheter</h1>
    <p class="ingress">
      Ställen i eller mellan kommunens reglementen och delegationsordningar som inte går ihop: två bestämmelser som säger
      olika saker om samma sak, hänvisningar till något som inte finns, och dokument som ligger ute flera gånger som
      gällande. De är redaktionens analys, granskad och publicerad av en utgivare, och kan anmälas till kommunen.
    </p>
  </header>

  <div class="filter" role="group" aria-label="Filter">
    <label>
      Typ
      <select v-model="typ" data-testid="filter-typ">
        <option value="">Alla</option>
        <option v-for="t in a?.typer ?? []" :key="t.id" :value="t.id">{{ t.namn }} ({{ tal(t.antal) }})</option>
      </select>
    </label>
    <label>
      Status
      <select v-model="status" data-testid="filter-status">
        <option value="">Alla</option>
        <option v-for="s in a?.statusar ?? []" :key="s.id" :value="s.id">{{ s.namn }} ({{ tal(s.antal) }})</option>
      </select>
    </label>
  </div>

  <p v-if="laddar && !a">Hämtar uppgifter…</p>
  <p v-else-if="fel" class="fel">Kunde inte hämta uppgifter: {{ fel }}</p>
  <section v-else-if="a" class="kort" aria-labelledby="lista-rubrik">
    <h2 id="lista-rubrik">
      {{ a.motstridigheter.length === 1 ? '1 motstridighet' : `${a.motstridigheter.length} motstridigheter` }}
    </h2>
    <p v-if="!a.motstridigheter.length" class="ingress" data-testid="inga">Inga publicerade motstridigheter matchar urvalet.</p>
    <Motstridighetskort v-for="m in a.motstridigheter" :key="m.id" :m="m">
      <div v-if="arRedaktor || arUtgivare" class="atgarder">
        <template v-if="arRedaktor">
          <button v-if="!formular[m.id]" type="button" data-testid="andra-status"
                  @click="formular[m.id] = { status: m.status, datum: m.statusdatum ?? '', anteckning: m.anteckning ?? '' }">
            Ändra status
          </button>
          <button type="button" data-testid="kopiera" @click="kopiera(m)">
            {{ kopierad === m.id ? 'Kopierad' : 'Kopiera sammanställning' }}
          </button>
        </template>
        <button v-if="arUtgivare && aterkallelse[m.id] === undefined" type="button" data-testid="aterkalla"
                @click="aterkallelse[m.id] = ''">
          Återkalla
        </button>
      </div>
      <form v-if="formular[m.id]" class="formular" data-testid="statusformular" @submit.prevent="spara(m)">
        <label>
          Status
          <select v-model="formular[m.id].status" data-testid="status">
            <option value="ny">Ny</option>
            <option value="anmald">Anmäld till kommunen</option>
            <option value="atgardad">Åtgärdad av kommunen</option>
          </select>
        </label>
        <label>
          Datum
          <input v-model="formular[m.id].datum" type="date" data-testid="datum" />
        </label>
        <label class="bred">
          Anteckning
          <input v-model="formular[m.id].anteckning" type="text" data-testid="anteckning-falt" />
        </label>
        <button type="submit" :disabled="sparar === m.id">Spara</button>
        <button type="button" @click="delete formular[m.id]">Avbryt</button>
      </form>
      <form v-if="aterkallelse[m.id] !== undefined" class="formular" @submit.prevent="aterkalla(m)">
        <label class="bred">
          Motivering
          <input v-model="aterkallelse[m.id]" type="text" data-testid="motivering" />
        </label>
        <button type="submit" :disabled="sparar === m.id">Återkalla</button>
        <button type="button" @click="delete aterkallelse[m.id]">Avbryt</button>
      </form>
      <p v-if="atgardsfel[m.id]" class="fel">{{ atgardsfel[m.id] }}</p>
    </Motstridighetskort>
  </section>
</template>

<style scoped>
.vyhuvud {
  margin-bottom: 16px;
}
.tillbaka {
  margin: 0 0 4px;
  font-size: 13px;
}
.ingress {
  color: var(--ink-secondary);
  max-width: 70ch;
}
.filter {
  display: flex;
  flex-wrap: wrap;
  gap: 16px;
  margin-bottom: 16px;
  font-size: 13px;
}
.filter label {
  display: flex;
  flex-direction: column;
  gap: 4px;
}
.kort {
  background: var(--surface);
  border: 1px solid var(--line);
  border-radius: var(--radius);
  padding: 24px;
  margin-bottom: 24px;
}
.kort h2 {
  margin-bottom: 12px;
}
.atgarder,
.formular {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  align-items: flex-end;
  margin-top: 8px;
  font-size: 13px;
}
.formular label {
  display: flex;
  flex-direction: column;
  gap: 4px;
}
.formular .bred {
  flex: 1 1 240px;
}
.fel {
  color: var(--status-critical);
}
</style>
