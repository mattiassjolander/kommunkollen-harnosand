<script setup lang="ts">
// Protokollavvikelser (#47): uppgifter i ett protokoll som inte stämmer med varandra, att anmäla till kommunen.
// De är möjliga fel i källan, till skillnad från tolkningens egna avvikelser under Avvikelser. Redaktören sätter
// status och kopierar en saklig sammanställning per protokoll. Filtren speglas i URL:en (design.md, Filter).
import { computed, inject, onMounted, reactive, ref, watch, type Ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import {
  EjInloggad,
  hamtaOrgan,
  hamtaProtokollavvikelser,
  sattProtokollavvikelsestatus,
  type Jag,
  type Organ,
  type Protokollavvikelse,
  type Protokollavvikelser,
  type Protokollavvikelsestatus,
} from '../../api'
import { datum, sammantradesdatum, tal } from '../../format'
import PolitikFlikar from '../../components/PolitikFlikar.vue'

const route = useRoute()
const router = useRouter()
const utloggad = inject<() => void>('utloggad', () => {})
const jag = inject<Ref<Jag | null>>('jag', ref(null))
const arRedaktor = computed(() => jag.value?.roller.includes('redaktor') ?? false)

function fraga(namn: string) {
  return computed<string>({
    get: () => (typeof route.query[namn] === 'string' ? (route.query[namn] as string) : ''),
    set: (v) => router.replace({ query: { ...route.query, [namn]: v || undefined } }),
  })
}
const valtOrgan = fraga('organ')
const fran = fraga('fran')
const till = fraga('till')
const typ = fraga('typ')
const status = fraga('status')

const organ = ref<Organ[]>([])
const ar = ref<number[]>([])
const a = ref<Protokollavvikelser | null>(null)
const laddar = ref(true)
const fel = ref<string | null>(null)
const omvant = computed(() => !!fran.value && !!till.value && Number(fran.value) > Number(till.value))

async function ladda() {
  if (omvant.value) return
  laddar.value = true
  fel.value = null
  try {
    a.value = await hamtaProtokollavvikelser({
      fran: fran.value,
      till: till.value,
      organ: valtOrgan.value || undefined,
      typ: typ.value || undefined,
      status: status.value || undefined,
    })
    if (!ar.value.length) ar.value = Array.from({ length: a.value.till - a.value.fran + 1 }, (_, i) => a.value!.fran + i)
  } catch (e) {
    if (e instanceof EjInloggad) return utloggad()
    fel.value = e instanceof Error ? e.message : String(e)
  } finally {
    laddar.value = false
  }
}
onMounted(async () => {
  try {
    organ.value = await hamtaOrgan()
  } catch (e) {
    if (e instanceof EjInloggad) return utloggad()
  }
  await ladda()
})
watch([valtOrgan, fran, till, typ, status], ladda)

const franAr = computed({ get: () => fran.value || String(a.value?.fran ?? ''), set: (v) => (fran.value = v) })
const tillAr = computed({ get: () => till.value || String(a.value?.till ?? ''), set: (v) => (till.value = v) })
const antal = computed(() => (a.value?.sammantraden ?? []).reduce((n, s) => n + s.avvikelser.length, 0))

// Redaktörens statusformulär, ett per avvikelse.
const formular = reactive<Record<number, { status: Protokollavvikelsestatus; datum: string; anteckning: string }>>({})
const sparar = ref<number | null>(null)
const statusfel = reactive<Record<number, string>>({})
function andra(x: Protokollavvikelse) {
  formular[x.id] = { status: x.status, datum: x.statusdatum ?? '', anteckning: x.anteckning ?? '' }
}
async function spara(x: Protokollavvikelse) {
  const f = formular[x.id]
  sparar.value = x.id
  delete statusfel[x.id]
  try {
    Object.assign(x, await sattProtokollavvikelsestatus(x.id, f.status, f.datum, f.anteckning))
    delete formular[x.id]
    // Sammanställningen och antalen beror på statusen.
    await ladda()
  } catch (e) {
    if (e instanceof EjInloggad) return utloggad()
    statusfel[x.id] = e instanceof Error ? e.message : String(e)
  } finally {
    sparar.value = null
  }
}

const kopierad = ref<number | null>(null)
async function kopiera(id: number, text: string) {
  try {
    await navigator.clipboard.writeText(text)
    kopierad.value = id
  } catch {
    // Utan tillgång till urklipp: texten visas ändå och kan markeras.
    kopierad.value = null
  }
}
</script>

<template>
  <header class="vyhuvud">
    <h1>Politik och beslut</h1>
    <p class="ingress">
      Uppgifter i protokollen som inte stämmer med varandra: röster som inte går ihop med antalet beslutande, olika
      parti för samma person, en ersättare för någon som själv är beslutande, paragrafer som saknas eller upprepas, parti
      som saknas i närvarolistan och namn som stavas olika. De kan anmälas till kommunen för rättning. Det som plattformen
      inte kunde läsa finns under <RouterLink to="/politik/avvikelser">Avvikelser</RouterLink>.
    </p>
  </header>
  <PolitikFlikar />

  <div class="filter" role="group" aria-label="Filter">
    <label>
      Organ
      <select v-model="valtOrgan" data-testid="filter-organ">
        <option value="">Alla organ</option>
        <option v-for="o in organ" :key="o.id" :value="o.id">{{ o.namn }}</option>
      </select>
    </label>
    <label>
      Från år
      <select v-model="franAr" data-testid="filter-fran">
        <option v-for="x in ar" :key="x" :value="String(x)">{{ x }}</option>
      </select>
    </label>
    <label>
      Till år
      <select v-model="tillAr" data-testid="filter-till">
        <option v-for="x in ar" :key="x" :value="String(x)">{{ x }}</option>
      </select>
    </label>
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

  <p v-if="omvant" class="fel" role="alert">Startåret kan inte vara efter slutåret.</p>
  <p v-else-if="fel" class="fel" role="alert">{{ fel }}</p>
  <p v-else-if="laddar && !a">Hämtar protokollavvikelser…</p>
  <template v-else-if="a">
    <section class="nyckeltal" aria-label="Antal per status">
      <div v-for="s in a.statusar" :key="s.id" class="tal" :data-status="s.id">
        <span class="varde">{{ tal(s.antal) }}</span>
        <span class="etikett">{{ s.namn }}</span>
      </div>
    </section>

    <section class="kort" aria-labelledby="lista-rubrik">
      <h2 id="lista-rubrik">{{ tal(antal) }} avvikelser i {{ tal(a.sammantraden.length) }} protokoll</h2>
      <p v-if="!a.sammantraden.length" class="saknas" data-testid="inga">Inga protokollavvikelser för urvalet.</p>
      <ul v-else class="protokoll">
        <li
          v-for="s in a.sammantraden"
          :id="`protokoll-${s.sammantrade.id}`"
          :key="s.sammantrade.id"
          data-testid="protokollavvikelser"
        >
          <div class="huvud">
            <RouterLink :to="`/politik/sammantraden/${s.sammantrade.id}`">
              {{ s.sammantrade.organ.namn }} {{ sammantradesdatum(s.sammantrade.datum) }}
            </RouterLink>
            <a :href="s.url" class="original" rel="noopener" target="_blank">Originalprotokollet</a>
          </div>
          <ul class="avvikelser">
            <li
              v-for="x in s.avvikelser"
              :key="x.id"
              data-testid="protokollavvikelse"
              :data-typ="x.typ"
              :data-status="x.status"
              :class="{ inaktuell: !x.hittas }"
            >
              <div class="rad">
                <span class="typ">{{ x.typnamn }}</span>
                <RouterLink v-if="x.paragraf !== null" :to="`/politik/sammantraden/${s.sammantrade.id}/paragraf/${x.paragraf}`">
                  {{ x.rubrik ? `§ ${x.paragraf} ${x.rubrik}` : `§ ${x.paragraf}` }}
                </RouterLink>
                <a v-if="x.sida" :href="x.lank" rel="noopener" target="_blank" data-testid="sida">sidan {{ x.sida }}</a>
                <span class="status" :data-status="x.status" data-testid="status">
                  {{ x.statusdatum ? `${x.statusnamn} ${datum(x.statusdatum)}` : x.statusnamn }}
                </span>
              </div>
              <p class="text">{{ x.text }}</p>
              <p v-if="x.anteckning" class="anteckning" data-testid="anteckning">{{ x.anteckning }}</p>
              <p v-if="x.reviderad" class="reviderad" data-testid="reviderad">
                ↻ Reviderad av källan: kommunen publicerade protokollet på nytt {{ datum(x.reviderad.datum) }}, och där
                finns avvikelsen inte längre.
              </p>
              <p v-else-if="!x.hittas" class="reviderad">Kontrollerna hittar inte längre avvikelsen i protokollet.</p>

              <template v-if="arRedaktor">
                <button v-if="!formular[x.id]" type="button" class="lank" data-testid="andra-status" @click="andra(x)">
                  Ändra status
                </button>
                <form v-else class="statusformular" @submit.prevent="spara(x)">
                  <label>
                    Status
                    <select v-model="formular[x.id].status" data-testid="ny-status">
                      <option v-for="st in a.statusar" :key="st.id" :value="st.id">{{ st.namn }}</option>
                    </select>
                  </label>
                  <label>
                    Datum
                    <input v-model="formular[x.id].datum" type="date" data-testid="statusdatum" />
                  </label>
                  <label class="bred">
                    Anteckning
                    <input v-model="formular[x.id].anteckning" type="text" data-testid="ny-anteckning" />
                  </label>
                  <button type="submit" :disabled="sparar === x.id" data-testid="spara-status">Spara</button>
                  <button type="button" class="lank" @click="delete formular[x.id]">Avbryt</button>
                  <p v-if="statusfel[x.id]" class="fel" role="alert">{{ statusfel[x.id] }}</p>
                </form>
              </template>
            </li>
          </ul>
          <details v-if="arRedaktor && s.sammanstallning" class="sammanstallning">
            <summary>Sammanställning till nämndsekreteraren</summary>
            <pre data-testid="sammanstallning">{{ s.sammanstallning }}</pre>
            <button type="button" data-testid="kopiera" @click="kopiera(s.sammantrade.id, s.sammanstallning)">
              {{ kopierad === s.sammantrade.id ? 'Kopierad' : 'Kopiera' }}
            </button>
          </details>
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
.filter {
  display: flex;
  gap: 16px;
  flex-wrap: wrap;
  margin-bottom: 16px;
}
.filter label,
.statusformular label {
  display: grid;
  gap: 4px;
  font-size: 13px;
  color: var(--ink-secondary);
}
.filter select,
.statusformular select,
.statusformular input {
  font: inherit;
  font-size: 14px;
  color: var(--ink);
  background: var(--surface);
  border: 1px solid var(--line);
  border-radius: var(--radius);
  padding: 6px 8px;
}
.nyckeltal {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(160px, 1fr));
  gap: 12px;
  margin-bottom: 16px;
}
.tal {
  background: var(--surface);
  border: 1px solid var(--line);
  border-radius: var(--radius);
  padding: 12px 16px;
  display: grid;
  gap: 2px;
}
.tal .varde {
  font-size: 24px;
  font-weight: 600;
  font-variant-numeric: tabular-nums;
}
.tal .etikett {
  font-size: 13px;
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
.protokoll {
  list-style: none;
  padding: 0;
  margin: 0;
}
.protokoll > li {
  padding: 12px 0;
  border-bottom: 1px solid var(--line);
}
.huvud {
  display: flex;
  flex-wrap: wrap;
  gap: 8px 12px;
  align-items: baseline;
  font-weight: 600;
}
.original {
  font-size: 12px;
  font-weight: 400;
}
.avvikelser {
  list-style: none;
  margin: 8px 0 0;
  padding: 0;
  font-size: 13px;
  color: var(--ink-secondary);
}
.avvikelser > li {
  padding: 8px 0 8px 12px;
  border-left: 2px solid var(--line);
  margin-bottom: 6px;
}
.avvikelser > li.inaktuell {
  opacity: 0.75;
}
.rad {
  display: flex;
  flex-wrap: wrap;
  gap: 4px 10px;
  align-items: baseline;
}
.typ {
  color: var(--ink);
  font-weight: 600;
}
.status {
  font-size: 12px;
  border: 1px solid var(--line-strong);
  border-radius: var(--radius);
  padding: 0 6px;
  color: var(--ink-secondary);
}
.status[data-status='anmald'] {
  border-color: var(--accent);
  color: var(--ink);
}
.status[data-status='rattad'] {
  border-style: solid;
  color: var(--ink);
  font-weight: 600;
}
.text {
  margin: 4px 0 0;
  color: var(--ink);
}
.anteckning,
.reviderad {
  margin: 4px 0 0;
  font-size: 12px;
  color: var(--ink-muted);
}
.reviderad {
  color: var(--ink-secondary);
}
.statusformular {
  display: flex;
  flex-wrap: wrap;
  gap: 8px 12px;
  align-items: end;
  margin-top: 8px;
}
.statusformular .bred {
  flex: 1 1 240px;
}
.statusformular .fel {
  flex-basis: 100%;
  margin: 0;
}
button {
  font: inherit;
  font-size: 13px;
  padding: 6px 12px;
  border: 1px solid var(--line-strong);
  border-radius: var(--radius);
  background: var(--surface);
  color: var(--ink);
  cursor: pointer;
}
button.lank {
  border: none;
  background: none;
  padding: 0;
  color: var(--accent);
  margin-top: 4px;
}
.sammanstallning {
  margin-top: 8px;
  font-size: 13px;
}
.sammanstallning pre {
  white-space: pre-wrap;
  font-family: inherit;
  background: var(--surface-raised, var(--surface));
  border: 1px solid var(--line);
  border-radius: var(--radius);
  padding: 8px 12px;
  color: var(--ink);
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
