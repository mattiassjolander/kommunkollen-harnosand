<script setup lang="ts">
// Redaktionella rättelser (#33): utkast → granskad → publicerad. En utgivare granskar och
// publicerar, men aldrig sin egen rättelse.
import { computed, inject, onMounted, ref, type Ref } from 'vue'
import {
  EjInloggad,
  granskaRattelse,
  hamtaRattelser,
  publiceraRattelse,
  taBortRattelse,
  type Jag,
  type Rattelse,
  type Rattelsestatus,
} from '../../api'
import { BEHANDLINGSTYPER } from '../../api'
import { datum, motionarstext, parti, rosttext } from '../../format'
import PolitikFlikar from '../../components/PolitikFlikar.vue'

const utloggad = inject<() => void>('utloggad', () => {})
const jag = inject<Ref<Jag | null>>('jag', ref(null))
const roller = computed(() => jag.value?.roller ?? [])
const behorig = computed(() => roller.value.includes('redaktor') || roller.value.includes('utgivare'))
const arUtgivare = computed(() => roller.value.includes('utgivare'))

const alla = ref<Rattelse[]>([])
const laddar = ref(true)
const fel = ref<string | null>(null)
const arbetar = ref<number | null>(null)

const STATUS: { status: Rattelsestatus; titel: string; text: string }[] = [
  { status: 'utkast', titel: 'Utkast', text: 'Väntar på att en utgivare granskar dem.' },
  { status: 'granskad', titel: 'Granskade', text: 'Väntar på att en utgivare publicerar dem.' },
  { status: 'publicerad', titel: 'Publicerade', text: 'Visas för läsarna med markering.' },
]

async function ladda() {
  try {
    alla.value = await hamtaRattelser()
  } catch (e) {
    if (e instanceof EjInloggad) return utloggad()
    fel.value = e instanceof Error ? e.message : String(e)
  } finally {
    laddar.value = false
  }
}
onMounted(() => (behorig.value ? ladda() : (laddar.value = false)))

async function steg(r: Rattelse, gor: (id: number) => Promise<unknown>) {
  arbetar.value = r.id
  fel.value = null
  try {
    await gor(r.id)
    await ladda()
  } catch (e) {
    if (e instanceof EjInloggad) return utloggad()
    fel.value = e instanceof Error ? e.message : String(e)
  } finally {
    arbetar.value = null
  }
}

const egen = (r: Rattelse) => r.redaktor === jag.value?.epost
const FALT: Record<string, string> = {
  rubrik: 'Rubrik', beslut: 'Beslut', diarienummer: 'Diarienummer', typ: 'Typ', rost: 'Röst', parti: 'Parti', motionarer: 'Motionärer',
}

function visa(r: Rattelse, v: unknown): string {
  if (v === null || v === undefined || (Array.isArray(v) && !v.length)) {
    return r.falt === 'parti' ? 'inget parti' : r.falt === 'typ' ? 'kunde inte klassas' : 'inget'
  }
  if (r.falt === 'motionarer') return motionarstext(v as { namn: string | null; parti: string | null }[])
  if (r.falt === 'parti') return parti(v as string)
  if (r.falt === 'rost') return rosttext(v as 'ja')
  if (r.falt === 'typ') return BEHANDLINGSTYPER.find((t) => t.id === v)?.namn ?? String(v)
  return Array.isArray(v) ? v.join(', ') : String(v)
}
function uppgift(r: Rattelse): string {
  if (r.objekt === 'rost') return `${FALT[r.falt]} för ${r.namn}, votering ${r.votering}`
  if (r.objekt === 'narvaro') return `Parti för ${r.namn} i närvarolistan`
  return FALT[r.falt]
}
function lank(r: Rattelse): string {
  const s = `/politik/sammantraden/${r.sammantrade.id}`
  return r.paragraf === null ? s : `${s}/paragraf/${r.paragraf}`
}
</script>

<template>
  <header class="vyhuvud">
    <h1>Politik och beslut</h1>
    <p class="ingress">
      Rättelser av automatiskt tolkade uppgifter. En redaktör skriver rättelsen, och en utgivare som inte är samma
      person granskar och publicerar den. Läsaren ser den rättade uppgiften med markering och vad tolkningen sa.
    </p>
  </header>
  <PolitikFlikar />

  <p v-if="!behorig" class="saknas">Rättelserna visas bara för redaktörer och utgivare.</p>
  <p v-else-if="laddar">Hämtar rättelser…</p>
  <template v-else>
    <p v-if="fel" class="fel" role="alert">{{ fel }}</p>
    <section v-for="g in STATUS" :key="g.status" :aria-labelledby="`rubrik-${g.status}`" class="grupp">
      <h2 :id="`rubrik-${g.status}`">
        {{ g.titel }} <span class="antal">({{ alla.filter((r) => r.status === g.status).length }})</span>
      </h2>
      <p class="anteckning">{{ g.text }}</p>
      <ul class="lista" :data-testid="`rattelser-${g.status}`">
        <li
          v-for="r in alla.filter((x) => x.status === g.status)"
          :key="r.id"
          class="kort"
          data-testid="rattelse"
          :data-id="r.id"
        >
          <p class="var">
            <RouterLink :to="lank(r)">
              {{ r.sammantrade.organ.namn }} {{ r.sammantrade.datum }}<template v-if="r.paragraf !== null">
                § {{ r.paragraf }} {{ r.rubrik }}</template
              >
            </RouterLink>
          </p>
          <dl class="falt">
            <dt>Uppgift</dt>
            <dd>{{ uppgift(r) }}</dd>
            <dt>Tolkningen</dt>
            <dd class="varde">{{ visa(r, r.ursprungligt) }}</dd>
            <dt>Rättat</dt>
            <dd class="varde" data-testid="nytt">{{ visa(r, r.nytt) }}</dd>
            <dt>Motivering</dt>
            <dd>{{ r.motivering }}</dd>
          </dl>
          <p class="anteckning">
            Skriven av {{ r.redaktor }} {{ datum(r.skapad) }}<template v-if="r.granskad_av">
              · granskad av {{ r.granskad_av }}</template
            ><template v-if="r.publicerad_av"> · publicerad av {{ r.publicerad_av }}</template>
          </p>
          <div class="knappar">
            <template v-if="arUtgivare && !egen(r)">
              <button
                v-if="r.status === 'utkast'"
                type="button"
                class="knapp primar"
                :disabled="arbetar === r.id"
                data-testid="granska"
                @click="steg(r, granskaRattelse)"
              >
                Markera som granskad
              </button>
              <button
                v-if="r.status === 'granskad'"
                type="button"
                class="knapp primar"
                :disabled="arbetar === r.id"
                data-testid="publicera"
                @click="steg(r, publiceraRattelse)"
              >
                Publicera
              </button>
            </template>
            <p v-else-if="egen(r) && r.status !== 'publicerad'" class="anteckning" data-testid="egen">
              Din egen rättelse. En annan utgivare godkänner den.
            </p>
            <button
              v-if="egen(r) && r.status === 'utkast'"
              type="button"
              class="knapp"
              :disabled="arbetar === r.id"
              data-testid="ta-bort"
              @click="steg(r, taBortRattelse)"
            >
              Ta bort utkastet
            </button>
          </div>
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
.varde {
  white-space: pre-line;
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
.saknas {
  color: var(--ink-muted);
  font-style: italic;
}
.fel {
  color: var(--status-critical);
}
</style>
