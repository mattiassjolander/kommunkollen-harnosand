<script setup lang="ts">
// Redaktionens granskning av motstridigheter i styrande dokument (#151). Förslagen kommer från insamlingen och från
// skillen harnosandskollen-styrande-dokument. En utgivare som inte läst in förslaget granskar och publicerar det, eller
// avvisar det med motivering. Publicerade motstridigheter vars dokument har ändrats står överst, tills en redaktör har
// tagit ställning. Filtren speglas i URL:en.
import { computed, inject, reactive, ref, watch, type Ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import {
  EjInloggad,
  avvisaMotstridighet,
  granskaMotstridighet,
  hamtaMotstridighetsforslag,
  publiceraMotstridighet,
  taStallningTillMotstridighet,
  type Jag,
  type Motstridighet,
  type Motstridighetsforslag,
} from '../../api'
import Motstridighetskort from '../../components/Motstridighetskort.vue'
import { datum } from '../../format'

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
const granskning = fraga('granskning')
const typ = fraga('typ')
const dokument = fraga('dokument')

const v = ref<Motstridighetsforslag | null>(null)
const laddar = ref(true)
const fel = ref<string | null>(null)

async function ladda() {
  laddar.value = true
  fel.value = null
  try {
    v.value = await hamtaMotstridighetsforslag({ granskning: granskning.value, typ: typ.value, dokument: dokument.value })
  } catch (e) {
    if (e instanceof EjInloggad) return utloggad()
    fel.value = e instanceof Error ? e.message : String(e)
  } finally {
    laddar.value = false
  }
}
watch([granskning, typ, dokument], ladda, { immediate: true })

const GRANSKNING: Record<string, string> = {
  utkast: 'Utkast',
  granskad: 'Granskad',
  publicerad: 'Publicerad',
  avvisad: 'Avvisad',
  aterkallad: 'Återkallad',
}

const egen = (m: Motstridighet) => !!jag.value && (m.redaktorer ?? []).includes(jag.value.epost)
const avvisning = reactive<Record<number, string>>({})
const sparar = ref<number | null>(null)
const atgardsfel = reactive<Record<number, string>>({})

async function utfor(m: Motstridighet, steg: () => Promise<unknown>) {
  sparar.value = m.id
  delete atgardsfel[m.id]
  try {
    await steg()
    delete avvisning[m.id]
    await ladda()
  } catch (e) {
    if (e instanceof EjInloggad) return utloggad()
    atgardsfel[m.id] = e instanceof Error ? e.message : String(e)
  } finally {
    sparar.value = null
  }
}
</script>

<template>
  <header class="vyhuvud">
    <h1>Motstridigheter</h1>
    <p class="ingress">
      Förslag till motstridigheter i reglementen och delegationsordningar, från insamlingen och från skillen. En utgivare
      som inte har läst in förslaget granskar och publicerar det, eller avvisar det. Formatet och kontrollerna står i
      docs/styrande-dokument.md. Det publicerade finns under
      <RouterLink to="/politik/styrande-dokument/motstridigheter">Styrande dokument → Motstridigheter</RouterLink>.
    </p>
  </header>

  <p v-if="laddar && !v">Hämtar uppgifter…</p>
  <p v-else-if="fel" class="fel">Kunde inte hämta uppgifter: {{ fel }}</p>
  <template v-else-if="v">
    <section v-if="v.andrade.length" class="kort" aria-labelledby="andrade-rubrik" data-testid="andrade">
      <h2 id="andrade-rubrik">Dokumentet har ändrats</h2>
      <p class="not">
        Ett berört dokument har fått en ny version efter att motstridigheten publicerades. Läs den nya versionen. Håller
        motstridigheten fortfarande, ta ställning så att märkningen tas bort. Annars återkallas den.
      </p>
      <Motstridighetskort v-for="m in v.andrade" :key="m.id" :m="m">
        <div class="atgarder">
          <button v-if="arRedaktor" type="button" :disabled="sparar === m.id" data-testid="ta-stallning"
                  @click="utfor(m, () => taStallningTillMotstridighet(m.id))">
            Håller fortfarande
          </button>
        </div>
        <p v-if="atgardsfel[m.id]" class="fel">{{ atgardsfel[m.id] }}</p>
      </Motstridighetskort>
    </section>

    <div class="filter" role="group" aria-label="Filter">
      <label>
        Granskning
        <select v-model="granskning" data-testid="filter-granskning">
          <option value="">Utkast och granskade</option>
          <option v-for="(namn, id) in GRANSKNING" :key="id" :value="id">{{ namn }}</option>
        </select>
      </label>
      <label>
        Typ
        <select v-model="typ" data-testid="filter-typ">
          <option value="">Alla</option>
          <option v-for="t in v.typer" :key="t.id" :value="t.id">{{ t.namn }}</option>
        </select>
      </label>
      <label>
        Dokument
        <select v-model="dokument" data-testid="filter-dokument">
          <option value="">Alla</option>
          <option v-for="d in v.dokument" :key="d.id" :value="String(d.id)">{{ d.titel }}</option>
        </select>
      </label>
    </div>

    <section class="kort" aria-labelledby="forslag-rubrik">
      <h2 id="forslag-rubrik">{{ v.forslag.length === 1 ? '1 förslag' : `${v.forslag.length} förslag` }}</h2>
      <p v-if="!v.forslag.length" class="not" data-testid="inga-forslag">Inga förslag matchar urvalet.</p>
      <Motstridighetskort v-for="m in v.forslag" :key="m.id" :m="m" data-testid="forslag">
        <p class="not" data-testid="granskning">
          {{ GRANSKNING[m.granskning ?? 'utkast'] }} ·
          {{ m.kalla === 'insamling' ? 'Från insamlingen' : `Inläst av ${m.redaktorer?.join(', ')}` }}
          {{ datum(m.skapad ?? null) }}
          <template v-if="m.granskad_av"> · Granskad av {{ m.granskad_av }}</template>
          <template v-if="m.avvisning"> · Avvisad: {{ m.avvisning }}</template>
          <template v-if="m.aterkallelse"> · Återkallad: {{ m.aterkallelse }}</template>
        </p>
        <div v-if="arUtgivare && (m.granskning === 'utkast' || m.granskning === 'granskad')" class="atgarder">
          <template v-if="egen(m)">
            <span class="not">Du har läst in förslaget och kan inte själv godkänna det.</span>
          </template>
          <button v-else-if="m.granskning === 'utkast'" type="button" :disabled="sparar === m.id" data-testid="granska"
                  @click="utfor(m, () => granskaMotstridighet(m.id))">
            Granskad
          </button>
          <button v-else type="button" :disabled="sparar === m.id" data-testid="publicera"
                  @click="utfor(m, () => publiceraMotstridighet(m.id))">
            Publicera
          </button>
          <button v-if="avvisning[m.id] === undefined" type="button" data-testid="avvisa" @click="avvisning[m.id] = ''">
            Avvisa
          </button>
        </div>
        <form v-if="avvisning[m.id] !== undefined" class="atgarder" @submit.prevent="utfor(m, () => avvisaMotstridighet(m.id, avvisning[m.id]))">
          <label class="bred">
            Motivering
            <input v-model="avvisning[m.id]" type="text" data-testid="motivering" />
          </label>
          <button type="submit" :disabled="sparar === m.id">Avvisa</button>
          <button type="button" @click="delete avvisning[m.id]">Avbryt</button>
        </form>
        <p v-if="atgardsfel[m.id]" class="fel">{{ atgardsfel[m.id] }}</p>
      </Motstridighetskort>
    </section>
  </template>
</template>

<style scoped>
.vyhuvud {
  margin-bottom: 16px;
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
.filter label,
.atgarder label {
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
.atgarder {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  align-items: flex-end;
  margin-top: 8px;
  font-size: 13px;
}
.bred {
  flex: 1 1 240px;
}
.not {
  color: var(--ink-muted);
  font-size: 13px;
  margin: 4px 0 0;
}
.fel {
  color: var(--status-critical);
}
</style>
