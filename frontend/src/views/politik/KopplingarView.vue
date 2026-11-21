<script setup lang="ts">
// Kopplingar mellan behandlingar (ADR-0002, ADR-0003). Fliken Förslag är kön, där en redaktör bekräftar
// eller avvisar. Flikarna Bekräftade och Avvisade visar tidigare beslut (#77): vem som beslutade och när,
// historiken, och ett formulär för att ändra beslutet med motivering. Flik, filter och vald koppling står i
// URL:en, så att ärendevyn kan länka hit.
import { computed, inject, nextTick, ref, watch, type Ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import {
  andraKopplingsbeslut,
  avvisaKoppling,
  bekraftaKoppling,
  EjInloggad,
  hamtaKopplingar,
  type Behandlingsref,
  type Jag,
  type Koppling,
  type Kopplingsbeslut,
} from '../../api'
import { datumTid, sammantradesdatum } from '../../format'
import Kopplingsmarkering from '../../components/Kopplingsmarkering.vue'
import PolitikFlikar from '../../components/PolitikFlikar.vue'

type Flik = 'forslag' | 'bekraftad' | 'avvisad'
type Beslut = Kopplingsbeslut['status']

const FLIKAR: { id: Flik; namn: string }[] = [
  { id: 'forslag', namn: 'Förslag' },
  { id: 'bekraftad', namn: 'Bekräftade' },
  { id: 'avvisad', namn: 'Avvisade' },
]
const BESLUT: Record<Beslut, string> = {
  forslag: 'Tillbaka till förslag',
  bekraftad: 'Bekräfta',
  avvisad: 'Avvisa',
}
const HISTORIK: Record<Beslut, string> = { forslag: 'Lades tillbaka som förslag', bekraftad: 'Bekräftad', avvisad: 'Avvisad' }

const route = useRoute()
const router = useRouter()
const utloggad = inject<() => void>('utloggad', () => {})
const jag = inject<Ref<Jag | null>>('jag', ref(null))
const arRedaktor = computed(() => jag.value?.roller.includes('redaktor') ?? false)

const flik = computed<Flik>(() => {
  const s = route.query.status
  return s === 'bekraftad' || s === 'avvisad' ? s : 'forslag'
})
const mina = computed(() => route.query.mina === '1')
const vald = computed(() => (route.query.koppling ? Number(route.query.koppling) : null))

const kopplingar = ref<Koppling[]>([])
const beslutade = ref<Koppling[]>([])
const laddar = ref(true)
const fel = ref<string | null>(null)
const arbetar = ref<number | null>(null)

// Formuläret för att ändra ett beslut: en koppling i taget.
const andrar = ref<number | null>(null)
const nyttBeslut = ref<Beslut>('bekraftad')
const motivering = ref('')

async function ladda() {
  if (!arRedaktor.value) {
    laddar.value = false
    return
  }
  laddar.value = true
  fel.value = null
  try {
    kopplingar.value = await hamtaKopplingar(flik.value, flik.value !== 'forslag' && mina.value)
  } catch (e) {
    if (e instanceof EjInloggad) return utloggad()
    fel.value = e instanceof Error ? e.message : String(e)
  } finally {
    laddar.value = false
  }
  if (vald.value !== null) {
    await nextTick()
    document.getElementById(`koppling-${vald.value}`)?.scrollIntoView({ block: 'center' })
    const k = kopplingar.value.find((x) => x.id === vald.value)
    if (k && k.status !== 'forslag') oppna(k)
  }
}
watch(() => [flik.value, mina.value, arRedaktor.value], ladda, { immediate: true })

function visa(f: Flik) {
  beslutade.value = []
  andrar.value = null
  router.push({ query: { ...(f === 'forslag' ? {} : { status: f }), ...(mina.value ? { mina: '1' } : {}) } })
}
function vaxlaMina(e: Event) {
  const pa = (e.target as HTMLInputElement).checked
  router.push({ query: { status: flik.value, ...(pa ? { mina: '1' } : {}) } })
}

async function besluta(k: Koppling, bekrafta: boolean) {
  arbetar.value = k.id
  fel.value = null
  try {
    const ny = await (bekrafta ? bekraftaKoppling(k.id) : avvisaKoppling(k.id))
    kopplingar.value = kopplingar.value.filter((f) => f.id !== k.id)
    beslutade.value = [ny, ...beslutade.value]
  } catch (e) {
    if (e instanceof EjInloggad) return utloggad()
    fel.value = e instanceof Error ? e.message : String(e)
  } finally {
    arbetar.value = null
  }
}

function alternativ(k: Koppling): Beslut[] {
  return (['bekraftad', 'avvisad', 'forslag'] as Beslut[]).filter((b) => b !== k.status)
}
function oppna(k: Koppling) {
  andrar.value = k.id
  nyttBeslut.value = alternativ(k)[0]
  motivering.value = ''
  fel.value = null
}
async function andra(k: Koppling) {
  if (!motivering.value.trim()) {
    fel.value = 'Skriv en motivering till ändringen.'
    return
  }
  arbetar.value = k.id
  fel.value = null
  try {
    const ny = await andraKopplingsbeslut(k.id, nyttBeslut.value, motivering.value)
    // Kopplingen flyttar till en annan flik. Den står kvar här med sitt nya beslut tills listan laddas om.
    kopplingar.value = kopplingar.value.map((x) => (x.id === k.id ? ny : x))
    andrar.value = null
  } catch (e) {
    if (e instanceof EjInloggad) return utloggad()
    fel.value = e instanceof Error ? e.message : String(e)
  } finally {
    arbetar.value = null
  }
}

const lank = (b: Behandlingsref) => `/politik/sammantraden/${b.sammantrade.id}/paragraf/${b.paragraf}`
const antalText = computed(() => {
  const n = kopplingar.value.length
  if (flik.value === 'forslag') return `${n} förslag att granska`
  return `${n} ${flik.value === 'bekraftad' ? 'bekräftade' : 'avvisade'} kopplingar${mina.value ? ' som du beslutade' : ''}`
})
</script>

<template>
  <header class="vyhuvud">
    <h1>Politik och beslut</h1>
    <p class="ingress">
      Kopplingar mellan behandlingar som plattformen inte kunnat göra säkert, till exempel när ett beslutsunderlag
      hänvisar till ett senare organ eller inte anger organet. En bekräftad koppling för ihop behandlingarna till ett
      ärende. Ett beslut kan ändras i efterhand med motivering, och alla beslut sparas.
    </p>
  </header>
  <PolitikFlikar />

  <p v-if="!arRedaktor" class="saknas">Kopplingarna visas bara för redaktörer.</p>
  <template v-else>
    <div class="verktyg">
      <nav class="statusflikar" aria-label="Kopplingarnas status">
        <button
          v-for="f in FLIKAR"
          :key="f.id"
          type="button"
          :class="{ aktiv: flik === f.id }"
          :aria-current="flik === f.id ? 'page' : undefined"
          :data-testid="`flik-${f.id}`"
          @click="visa(f.id)"
        >
          {{ f.namn }}
        </button>
      </nav>
      <label v-if="flik !== 'forslag'" class="filter">
        <input type="checkbox" :checked="mina" data-testid="mina-beslut" @change="vaxlaMina" /> Mina beslut
      </label>
    </div>

    <p v-if="laddar">Hämtar kopplingar…</p>
    <template v-else>
      <p v-if="fel" class="fel" role="alert">{{ fel }}</p>
      <p class="antal" data-testid="antal-forslag">{{ antalText }}</p>

      <ul class="ko" data-testid="kopplingsko">
        <li
          v-for="k in kopplingar"
          :id="`koppling-${k.id}`"
          :key="k.id"
          class="kort"
          :class="{ vald: k.id === vald }"
          :data-testid="flik === 'forslag' ? 'kopplingsforslag' : 'beslutad-koppling'"
          :data-koppling="k.id"
        >
          <div class="par">
            <div v-for="(b, i) in [k.fran, k.till]" :key="i" class="sida">
              <p class="anteckning">
                {{ i === 0 ? 'Tidigare' : 'Senare' }} · {{ b.sammantrade.organ.namn }},
                {{ sammantradesdatum(b.sammantrade.datum) }}
              </p>
              <RouterLink :to="lank(b)">§ {{ b.paragraf }} {{ b.rubrik }}</RouterLink>
            </div>
          </div>
          <p class="grund"><Kopplingsmarkering :koppling="k" /></p>

          <div v-if="flik === 'forslag' && k.status === 'forslag'" class="knappar">
            <button
              type="button"
              class="knapp primar"
              :disabled="arbetar === k.id"
              data-testid="bekrafta"
              @click="besluta(k, true)"
            >
              Bekräfta koppling
            </button>
            <button type="button" class="knapp" :disabled="arbetar === k.id" data-testid="avvisa" @click="besluta(k, false)">
              Avvisa
            </button>
          </div>

          <template v-else>
            <p v-if="k.redaktor" class="beslutsfattare" data-testid="beslutsfattare">
              Beslutat av {{ k.redaktor }}, {{ datumTid(k.beslutad) }}
            </p>
            <details v-if="k.historik.length" class="historik" :open="k.id === vald || k.historik.length > 1">
              <summary>Historik ({{ k.historik.length }} beslut)</summary>
              <ol data-testid="historik">
                <li v-for="(h, i) in k.historik" :key="i" :data-status="h.status">
                  <strong>{{ HISTORIK[h.status] }}</strong> av {{ h.redaktor }}, {{ datumTid(h.tid) }}
                  <span v-if="h.motivering" class="motivering">: ”{{ h.motivering }}”</span>
                </li>
              </ol>
            </details>

            <button
              v-if="andrar !== k.id && k.status !== 'automatisk'"
              type="button"
              class="knapp"
              data-testid="andra-beslut"
              @click="oppna(k)"
            >
              Ändra beslut
            </button>
            <form v-else-if="andrar === k.id" class="andra" data-testid="andra-formular" @submit.prevent="andra(k)">
              <fieldset>
                <legend>Nytt beslut</legend>
                <label v-for="b in alternativ(k)" :key="b">
                  <input v-model="nyttBeslut" type="radio" :value="b" name="nytt-beslut" /> {{ BESLUT[b] }}
                </label>
              </fieldset>
              <label class="motiveringsfalt">
                Motivering (krävs)
                <textarea v-model="motivering" rows="2" required data-testid="motivering" />
              </label>
              <div class="knappar">
                <button type="submit" class="knapp primar" :disabled="arbetar === k.id" data-testid="spara-beslut">
                  Spara beslut
                </button>
                <button type="button" class="knapp" @click="andrar = null">Avbryt</button>
              </div>
            </form>
          </template>
        </li>
      </ul>
      <p v-if="!kopplingar.length && flik !== 'forslag'" class="saknas">Inga kopplingar med det beslutet.</p>

      <section v-if="beslutade.length" aria-labelledby="besl-rubrik">
        <h2 id="besl-rubrik">Beslutade nu</h2>
        <ul class="lista" data-testid="beslutade">
          <li v-for="k in beslutade" :key="k.id">
            <RouterLink :to="lank(k.till)">{{ k.till.sammantrade.organ.namn }} § {{ k.till.paragraf }}</RouterLink>
            ← {{ k.fran.sammantrade.organ.namn }} § {{ k.fran.paragraf }}
            <span class="anteckning"><Kopplingsmarkering :koppling="k" /></span>
          </li>
        </ul>
      </section>
    </template>
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
.verktyg {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 8px;
}
.statusflikar {
  display: flex;
  gap: 4px;
  border-bottom: 1px solid var(--line);
}
.statusflikar button {
  font: inherit;
  font-size: 13px;
  padding: 6px 12px;
  border: none;
  border-bottom: 2px solid transparent;
  background: none;
  color: var(--ink-secondary);
  cursor: pointer;
}
.statusflikar button.aktiv {
  color: var(--ink);
  font-weight: 600;
  border-bottom-color: var(--accent);
}
.filter {
  font-size: 13px;
  color: var(--ink-secondary);
}
.antal {
  font-size: 13px;
  color: var(--ink-secondary);
}
.ko {
  list-style: none;
  margin: 0 0 24px;
  padding: 0;
  display: grid;
  gap: 16px;
}
.kort {
  background: var(--surface);
  border: 1px solid var(--line);
  border-radius: var(--radius);
  padding: 20px 24px;
}
.kort.vald {
  border-color: var(--accent);
}
.par {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 24px;
}
@media (max-width: 800px) {
  .par {
    grid-template-columns: 1fr;
  }
}
.sida a {
  color: var(--accent);
}
.anteckning {
  font-size: 12px;
  color: var(--ink-muted);
  margin: 0 0 2px;
}
.grund {
  margin: 12px 0;
}
.beslutsfattare {
  font-size: 13px;
  color: var(--ink-secondary);
  margin: 0 0 8px;
}
.historik {
  font-size: 13px;
  margin: 0 0 12px;
}
.historik ol {
  margin: 6px 0 0;
  padding-left: 20px;
}
.historik li {
  padding: 2px 0;
}
.motivering {
  color: var(--ink-secondary);
}
.andra {
  display: grid;
  gap: 10px;
  font-size: 13px;
  max-width: 60ch;
}
.andra fieldset {
  border: none;
  margin: 0;
  padding: 0;
  display: flex;
  flex-wrap: wrap;
  gap: 4px 16px;
}
.andra legend {
  font-weight: 600;
  margin-bottom: 4px;
}
.motiveringsfalt {
  display: grid;
  gap: 4px;
}
.motiveringsfalt textarea {
  font: inherit;
  padding: 6px 8px;
  border: 1px solid var(--line-strong);
  border-radius: var(--radius);
  background: var(--surface);
  color: var(--ink);
}
.knappar {
  display: flex;
  gap: 8px;
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
  cursor: default;
}
.lista {
  list-style: none;
  margin: 0;
  padding: 0;
  font-size: 13px;
}
.lista li {
  padding: 6px 0;
  border-bottom: 1px solid var(--line);
}
.lista .anteckning {
  display: block;
}
.saknas {
  color: var(--ink-muted);
  font-style: italic;
}
.fel {
  color: var(--status-critical);
}
</style>
