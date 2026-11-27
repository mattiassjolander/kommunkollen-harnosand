<script setup lang="ts">
// Fastställda partitillhörigheter (#100, ADR-0006): utkast → granskad → publicerad, som rättelser. En utgivare
// granskar och publicerar, men aldrig sin egen period. En granskad eller publicerad period ändras genom en ny
// version, och en utgivare kan återkalla en publicerad. En utgivare kan också kassera ett utkast eller en granskad
// period som inte ska publiceras, till exempel en dubblett (#202). Ersatta, återkallade och kasserade perioder
// visas som historik.
import { computed, inject, onMounted, ref, type Ref } from 'vue'
import {
  aterkallaPartitillhorighet,
  EjInloggad,
  granskaPartitillhorighet,
  granskaPeriodbatch,
  hamtaPartitillhorigheter,
  kasseraPartitillhorighet,
  publiceraPartitillhorighet,
  publiceraPeriodbatch,
  taBortPartitillhorighet,
  type Jag,
  type Partitillhorighet,
  type Periodstatus,
} from '../../api'
import { datum } from '../../format'
import Partimarkering from '../../components/Partimarkering.vue'
import Krocklista from '../../components/Krocklista.vue'
import Periodforslag from '../../components/Periodforslag.vue'
import Periodpersoner from '../../components/Periodpersoner.vue'
import Periodformular from '../../components/Periodformular.vue'

const utloggad = inject<() => void>('utloggad', () => {})
const jag = inject<Ref<Jag | null>>('jag', ref(null))
const roller = computed(() => jag.value?.roller ?? [])
const behorig = computed(() => roller.value.includes('redaktor') || roller.value.includes('utgivare'))
const arUtgivare = computed(() => roller.value.includes('utgivare'))
const arRedaktor = computed(() => roller.value.includes('redaktor'))

const alla = ref<Partitillhorighet[]>([])
const laddar = ref(true)
const fel = ref<string | null>(null)
const arbetar = ref<number | null>(null)
// En ny version, en återkallelse eller en kassering, för en period i taget.
const andras = ref<{ id: number; lage: 'version' | 'aterkalla' | 'kassera' } | null>(null)
const aterkallelse = ref('')

const STATUS: { status: Periodstatus; titel: string; text: string }[] = [
  { status: 'utkast', titel: 'Utkast', text: 'Väntar på att en utgivare granskar dem.' },
  { status: 'granskad', titel: 'Granskade', text: 'Väntar på att en utgivare publicerar dem.' },
  { status: 'publicerad', titel: 'Publicerade', text: 'Gäller vid sammanträden under perioden, med markering.' },
  { status: 'ersatt', titel: 'Ersatta versioner', text: 'Har ersatts av en nyare version. Bevaras som historik.' },
  {
    status: 'aterkallad',
    titel: 'Återkallade och kasserade',
    text: 'Gäller inte längre eller publicerades aldrig. Protokollens uppgifter gäller.',
  },
]

// Personerna och krockarna (#100, del 3) räknas om när perioderna ändras.
const personlista = ref<InstanceType<typeof Periodpersoner> | null>(null)
const krocklista = ref<InstanceType<typeof Krocklista> | null>(null)

async function ladda() {
  try {
    alla.value = await hamtaPartitillhorigheter()
    personlista.value?.ladda()
    krocklista.value?.ladda()
  } catch (e) {
    if (e instanceof EjInloggad) return utloggad()
    fel.value = e instanceof Error ? e.message : String(e)
  } finally {
    laddar.value = false
  }
}
onMounted(() => (behorig.value ? ladda() : (laddar.value = false)))

async function steg(t: Partitillhorighet, gor: (id: number) => Promise<unknown>) {
  arbetar.value = t.id
  fel.value = null
  try {
    await gor(t.id)
    andras.value = null
    aterkallelse.value = ''
    await ladda()
  } catch (e) {
    if (e instanceof EjInloggad) return utloggad()
    fel.value = e instanceof Error ? e.message : String(e)
  } finally {
    arbetar.value = null
  }
}

const egen = (t: Partitillhorighet) => t.redaktor === jag.value?.epost
const vantar = (t: Partitillhorighet) =>
  alla.value.some((x) => x.ersatter_id === t.id && ['utkast', 'granskad'].includes(x.status))
const kanNyVersion = (t: Partitillhorighet) =>
  arRedaktor.value && ['granskad', 'publicerad'].includes(t.status) && !vantar(t)
// Batcher (#100, del 2): perioder som bekräftades tillsammans granskas och publiceras tillsammans.
const meddelande = ref<string | null>(null)
function skapade(batch: number, antal: number) {
  meddelande.value = `${antal} ${antal === 1 ? 'period är sparad' : 'perioder är sparade'} som utkast i batch ${batch}.`
  ladda()
}
function batcher(status: Periodstatus) {
  const ut = new Map<number, Partitillhorighet[]>()
  for (const t of alla.value) if (t.batch !== null && t.status === status) ut.set(t.batch, [...(ut.get(t.batch) ?? []), t])
  return [...ut].map(([batch, perioder]) => ({ batch, perioder, egen: perioder.some(egen) }))
}
async function batchsteg(batch: number, gor: (b: number) => Promise<unknown>) {
  arbetar.value = -batch
  fel.value = null
  try {
    await gor(batch)
    await ladda()
  } catch (e) {
    if (e instanceof EjInloggad) return utloggad()
    fel.value = e instanceof Error ? e.message : String(e)
  } finally {
    arbetar.value = null
  }
}

const ersatter = (t: Partitillhorighet) => alla.value.find((x) => x.id === t.ersatter_id)
</script>

<template>
  <header class="vyhuvud">
    <h1>Partitillhörighet</h1>
    <p class="ingress">
      Partitillhörighet som redaktionen fastställer för en person under en period. En redaktör registrerar perioden
      på personens sida, och en utgivare som inte är samma person granskar och publicerar den. Perioden gäller före
      protokollens uppgift, och läsaren ser vad protokollet anger.
    </p>
  </header>

  <p v-if="!behorig" class="saknas">Partitillhörigheterna visas bara för redaktörer och utgivare.</p>
  <p v-else-if="laddar">Hämtar partitillhörigheter…</p>
  <template v-else>
    <p v-if="fel" class="fel" role="alert">{{ fel }}</p>
    <p v-if="meddelande" class="meddelande" role="status" data-testid="batch-sparad">{{ meddelande }}</p>
    <Periodpersoner ref="personlista" @utloggad="utloggad" />
    <Krocklista ref="krocklista" @utloggad="utloggad" />
    <Periodforslag v-if="arRedaktor" @skapade="skapade" @utloggad="utloggad" />
    <section v-for="g in STATUS" :key="g.status" :aria-labelledby="`rubrik-${g.status}`" class="grupp">
      <h2 :id="`rubrik-${g.status}`">
        {{ g.titel }} <span class="antal">({{ alla.filter((t) => t.status === g.status).length }})</span>
      </h2>
      <p class="anteckning">{{ g.text }}</p>
      <template v-if="arUtgivare && (g.status === 'utkast' || g.status === 'granskad')">
        <div v-for="b in batcher(g.status)" :key="b.batch" class="batch" data-testid="batch" :data-batch="b.batch">
          <span>Batch {{ b.batch }}: {{ b.perioder.length }} {{ b.perioder.length === 1 ? 'period' : 'perioder' }}</span>
          <button
            v-if="!b.egen"
            type="button"
            class="knapp primar"
            :disabled="arbetar === -b.batch"
            :data-testid="g.status === 'utkast' ? 'granska-batch' : 'publicera-batch'"
            @click="batchsteg(b.batch, g.status === 'utkast' ? granskaPeriodbatch : publiceraPeriodbatch)"
          >
            {{ g.status === 'utkast' ? 'Markera hela batchen som granskad' : 'Publicera hela batchen' }}
          </button>
          <span v-else class="anteckning">Din egen batch. En annan utgivare godkänner den.</span>
        </div>
      </template>
      <ul class="lista" :data-testid="`perioder-${g.status}`">
        <li
          v-for="t in alla.filter((x) => x.status === g.status)"
          :id="`period-${t.id}`"
          :key="t.id"
          class="kort"
          data-testid="period"
          :data-id="t.id"
        >
          <p class="var">
            <RouterLink :to="`/politik/ledamoter/${t.ledamot.id}`">{{ t.ledamot.namn }}</RouterLink>
          </p>
          <dl class="falt">
            <dt>Parti</dt>
            <dd><Partimarkering :parti="t.parti" /></dd>
            <dt>Period</dt>
            <dd class="tal">{{ t.fran }} – {{ t.till ?? 'tills vidare' }}</dd>
            <dt>Motivering</dt>
            <dd>{{ t.motivering }}</dd>
            <template v-if="ersatter(t)">
              <dt>Ersätter</dt>
              <dd>{{ ersatter(t)!.parti }}, {{ ersatter(t)!.fran }} – {{ ersatter(t)!.till ?? 'tills vidare' }}</dd>
            </template>
            <template v-if="t.aterkallad">
              <dt>{{ t.publicerad ? 'Återkallad' : 'Kasserad' }}</dt>
              <dd data-testid="aterkallelse">{{ t.aterkallelse }} ({{ t.aterkallad_av }} {{ datum(t.aterkallad) }})</dd>
            </template>
          </dl>
          <p class="anteckning">
            <template v-if="t.batch !== null">Batch {{ t.batch }} · </template>Registrerad av {{ t.redaktor }} {{ datum(t.skapad) }}<template v-if="t.granskad_av">
              · granskad av {{ t.granskad_av }}</template
            ><template v-if="t.publicerad_av"> · publicerad av {{ t.publicerad_av }}</template>
          </p>
          <div class="knappar">
            <template v-if="arUtgivare && !egen(t)">
              <button
                v-if="t.status === 'utkast'"
                type="button"
                class="knapp primar"
                :disabled="arbetar === t.id"
                data-testid="granska"
                @click="steg(t, granskaPartitillhorighet)"
              >
                Markera som granskad
              </button>
              <button
                v-if="t.status === 'granskad'"
                type="button"
                class="knapp primar"
                :disabled="arbetar === t.id"
                data-testid="publicera"
                @click="steg(t, publiceraPartitillhorighet)"
              >
                Publicera
              </button>
            </template>
            <p v-else-if="egen(t) && ['utkast', 'granskad'].includes(t.status)" class="anteckning" data-testid="egen">
              Din egen registrering. En annan utgivare godkänner den.
            </p>
            <button
              v-if="arUtgivare && ['utkast', 'granskad'].includes(t.status) && andras?.id !== t.id"
              type="button"
              class="knapp"
              data-testid="kassera"
              @click="(andras = { id: t.id, lage: 'kassera' }), (aterkallelse = '')"
            >
              Kassera
            </button>
            <button
              v-if="egen(t) && t.status === 'utkast'"
              type="button"
              class="knapp"
              :disabled="arbetar === t.id"
              data-testid="ta-bort"
              @click="steg(t, taBortPartitillhorighet)"
            >
              Ta bort utkastet
            </button>
            <button
              v-if="kanNyVersion(t) && andras?.id !== t.id"
              type="button"
              class="knapp"
              data-testid="ny-version"
              @click="andras = { id: t.id, lage: 'version' }"
            >
              Ändra genom ny version
            </button>
            <p v-else-if="vantar(t)" class="anteckning" data-testid="version-vantar">En ny version väntar på granskning.</p>
            <button
              v-if="arUtgivare && t.status === 'publicerad' && andras?.id !== t.id"
              type="button"
              class="knapp"
              data-testid="aterkalla"
              @click="(andras = { id: t.id, lage: 'aterkalla' }), (aterkallelse = '')"
            >
              Återkalla
            </button>
          </div>
          <Periodformular
            v-if="andras?.id === t.id && andras.lage === 'version'"
            :ledamot-id="t.ledamot.id"
            :ersatter="t"
            @sparad="andras = null; ladda()"
            @avbryt="andras = null"
            @utloggad="utloggad"
          />
          <form
            v-else-if="andras?.id === t.id && andras.lage === 'kassera'"
            class="aterkalla"
            data-testid="kassera-formular"
            @submit.prevent="steg(t, (id) => kasseraPartitillhorighet(id, aterkallelse))"
          >
            <label>
              Varför perioden kasseras
              <textarea v-model="aterkallelse" rows="2" required data-testid="kassera-motivering" />
            </label>
            <p class="anteckning">
              Perioden publiceras inte. Den finns kvar under Återkallade och kasserade, med motiveringen.
            </p>
            <div class="knappar">
              <button type="submit" class="knapp primar" :disabled="arbetar === t.id" data-testid="spara-kassering">
                Kassera perioden
              </button>
              <button type="button" class="knapp" @click="andras = null">Avbryt</button>
            </div>
          </form>
          <form
            v-else-if="andras?.id === t.id"
            class="aterkalla"
            data-testid="aterkalla-formular"
            @submit.prevent="steg(t, (id) => aterkallaPartitillhorighet(id, aterkallelse))"
          >
            <label>
              Varför perioden återkallas
              <textarea v-model="aterkallelse" rows="2" required data-testid="aterkalla-motivering" />
            </label>
            <p class="anteckning">Perioden slutar gälla direkt, och protokollens uppgifter gäller igen.</p>
            <div class="knappar">
              <button type="submit" class="knapp primar" :disabled="arbetar === t.id" data-testid="spara-aterkallelse">
                Återkalla perioden
              </button>
              <button type="button" class="knapp" @click="andras = null">Avbryt</button>
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
.grupp {
  margin-bottom: 32px;
}
.antal {
  color: var(--ink-muted);
  font-weight: 400;
}
.lista {
  list-style: none;
  margin: 12px 0 0;
  padding: 0;
  display: grid;
  gap: 12px;
}
.kort {
  background: var(--surface);
  border: 1px solid var(--line);
  border-radius: var(--radius);
  padding: 16px 24px;
}
.var {
  margin: 0 0 8px;
}
.var a {
  color: var(--accent);
}
.falt {
  display: grid;
  grid-template-columns: max-content 1fr;
  gap: 4px 16px;
  margin: 0 0 8px;
  font-size: 13px;
  max-width: 90ch;
}
.falt dt {
  color: var(--ink-secondary);
  font-weight: 600;
}
.falt dd {
  margin: 0;
}
.anteckning {
  font-size: 12px;
  color: var(--ink-muted);
  margin: 0;
}
.knappar {
  display: flex;
  gap: 8px;
  align-items: center;
  margin-top: 8px;
}
.knapp {
  font: inherit;
  font-size: 13px;
  padding: 6px 14px;
  border-radius: var(--radius);
  border: 1px solid var(--line);
  background: var(--surface);
  color: var(--ink);
  cursor: pointer;
}
.knapp.primar {
  background: var(--accent);
  border-color: var(--accent);
  color: var(--surface);
}
.knapp:disabled {
  opacity: 0.6;
}
.aterkalla {
  display: grid;
  gap: 10px;
  max-width: 640px;
  margin-top: 12px;
  padding-top: 12px;
  border-top: 1px solid var(--line);
}
.aterkalla label {
  display: grid;
  gap: 4px;
  font-size: 13px;
  color: var(--ink-secondary);
}
.aterkalla textarea {
  font: inherit;
  font-size: 14px;
  color: var(--ink);
  background: var(--surface);
  border: 1px solid var(--line);
  border-radius: var(--radius);
  padding: 6px 8px;
}
.batch {
  display: flex;
  gap: 12px;
  align-items: center;
  margin: 8px 0 0;
  font-size: 13px;
}
.meddelande {
  color: var(--ink-secondary);
}
.saknas {
  color: var(--ink-muted);
  font-style: italic;
}
.fel {
  color: var(--status-critical);
}
</style>
