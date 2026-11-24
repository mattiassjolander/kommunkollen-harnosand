<script setup lang="ts">
// Redaktionella rättelser (#33): utkast → granskad → publicerad. En utgivare granskar och
// publicerar, men aldrig sin egen rättelse. En granskad eller publicerad rättelse ändras genom en ny version, och
// en utgivare kan återkalla en publicerad. Ersatta och återkallade versioner visas som historik (#74).
import { computed, inject, nextTick, onMounted, ref, type Ref } from 'vue'
import { useRoute } from 'vue-router'
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
import { FELET_I } from '../../api'
import { datum, rattelseuppgift, rattelsevarde } from '../../format'
import Rattelseandring from '../../components/Rattelseandring.vue'

const route = useRoute()
const utloggad = inject<() => void>('utloggad', () => {})
const jag = inject<Ref<Jag | null>>('jag', ref(null))
const roller = computed(() => jag.value?.roller ?? [])
const behorig = computed(() => roller.value.includes('redaktor') || roller.value.includes('utgivare'))
const arUtgivare = computed(() => roller.value.includes('utgivare'))
const arRedaktor = computed(() => roller.value.includes('redaktor'))
// Formuläret för en ny version eller en återkallelse, för en rättelse i taget.
const andras = ref<{ id: number; lage: 'version' | 'aterkalla' } | null>(null)
const vantar = (r: Rattelse) => alla.value.some((x) => x.ersatter_id === r.id && ['utkast', 'granskad'].includes(x.status))
const kanNyVersion = (r: Rattelse) =>
  ['granskad', 'publicerad'].includes(r.status) && !vantar(r) && (arRedaktor.value || r.falt === 'motionarer')

const alla = ref<Rattelse[]>([])
const laddar = ref(true)
const fel = ref<string | null>(null)
const arbetar = ref<number | null>(null)

const STATUS: { status: Rattelsestatus; titel: string; text: string }[] = [
  { status: 'utkast', titel: 'Utkast', text: 'Väntar på att en utgivare granskar dem.' },
  { status: 'granskad', titel: 'Granskade', text: 'Väntar på att en utgivare publicerar dem.' },
  { status: 'publicerad', titel: 'Publicerade', text: 'Visas för läsarna med markering.' },
  { status: 'ersatt', titel: 'Ersatta versioner', text: 'Har ersatts av en nyare version. Bevaras som historik.' },
  { status: 'aterkallad', titel: 'Återkallade', text: 'Gäller inte längre. Tolkningen gäller igen.' },
]

async function ladda() {
  try {
    alla.value = await hamtaRattelser()
    // En länk från listan över felaktigheter pekar på en rättelse.
    if (route.hash) nextTick(() => document.getElementById(route.hash.slice(1))?.scrollIntoView())
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
const visa = (r: Rattelse, v: unknown) => rattelsevarde(r.falt, v)
const uppgift = (r: Rattelse) => rattelseuppgift(r)
function lank(r: Rattelse): string {
  const s = `/politik/sammantraden/${r.sammantrade.id}`
  return r.paragraf === null ? s : `${s}/paragraf/${r.paragraf}`
}
</script>

<template>
  <header class="vyhuvud">
    <h1>Rättelser</h1>
    <p class="ingress">
      Rättelser av automatiskt tolkade uppgifter. En redaktör skriver rättelsen, och en utgivare som inte är samma
      person granskar och publicerar den. Läsaren ser den rättade uppgiften med markering och vad tolkningen sa.
    </p>
  </header>

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
          :id="`rattelse-${r.id}`"
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
            <dt>Felet finns</dt>
            <dd data-testid="felet-i" :data-felet-i="r.felet_i ?? 'ej_angivet'">{{ FELET_I[r.felet_i ?? 'ej_angivet'] }}</dd>
            <template v-if="r.aterkallad">
              <dt>Återkallad</dt>
              <dd data-testid="aterkallelse">{{ r.aterkallelse }} ({{ r.aterkallad_av }} {{ datum(r.aterkallad) }})</dd>
            </template>
          </dl>
          <details v-if="r.tidigare.length" class="tidigare" data-testid="tidigare-versioner">
            <summary>{{ r.ersatter_id ? 'Ersätter' : 'Tidigare versioner' }} ({{ r.tidigare.length }})</summary>
            <ol>
              <li v-for="t in r.tidigare" :key="t.id" :data-status="t.status">
                {{ visa(t, t.nytt) }}, {{ FELET_I[t.felet_i ?? 'ej_angivet'].toLowerCase() }}.
                {{ t.motivering }} <span class="anteckning">({{ t.status }})</span>
              </li>
            </ol>
          </details>
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
            <button
              v-if="kanNyVersion(r) && andras?.id !== r.id"
              type="button"
              class="knapp"
              data-testid="ny-version"
              @click="andras = { id: r.id, lage: 'version' }"
            >
              {{ r.felet_i ? 'Ändra genom ny version' : 'Ange var felet finns' }}
            </button>
            <p v-else-if="vantar(r)" class="anteckning" data-testid="version-vantar">En ny version väntar på granskning.</p>
            <button
              v-if="arUtgivare && r.status === 'publicerad' && andras?.id !== r.id"
              type="button"
              class="knapp"
              data-testid="aterkalla"
              @click="andras = { id: r.id, lage: 'aterkalla' }"
            >
              Återkalla
            </button>
          </div>
          <Rattelseandring
            v-if="andras?.id === r.id"
            :rattelse="r"
            :lage="andras.lage"
            @klar="andras = null; ladda()"
            @avbryt="andras = null"
            @utloggad="utloggad"
          />
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
.tidigare {
  font-size: 13px;
  margin-top: 8px;
}
.tidigare ol {
  margin: 4px 0 0;
  padding-left: 18px;
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
