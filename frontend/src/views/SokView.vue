<script setup lang="ts">
// Sidan Sök (#142): en resultatlista över behandlingar, protokollsidor, budgetförslag, ärenden, ledamöter och
// kallelsepunkter. Antalet per typ är filter, och organ, år och sortering speglas i URL:en (design.md, Filter).
// Varje träff länkar till sin sida på plattformen och till sidan i källdokumentet, med samma markeringar som
// sidan den länkar till. Sidan svarar aldrig med något eget, den hittar och länkar till källorna (ADR-0002).
import { computed, inject, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import {
  EjInloggad,
  ForManga,
  hamtaOrgan,
  sok,
  type Organ,
  type Soksortering,
  type Soksvar,
  type Soktraff,
  type Soktyp,
} from '../api'
import { datum } from '../format'
import Felaktighetsmarkering from '../components/Felaktighetsmarkering.vue'
import Tolkningsmarkering from '../components/Tolkningsmarkering.vue'

const route = useRoute()
const router = useRouter()
const utloggad = inject<() => void>('utloggad', () => {})

const TYPNAMN: Record<Soktyp, string> = {
  behandling: 'Behandlingar',
  protokollsida: 'Protokollsidor',
  budgetforslag: 'Budgetförslag',
  arende: 'Ärenden',
  ledamot: 'Ledamöter',
  kallelsepunkt: 'Kallelsepunkter',
}
const ETIKETT: Record<Soktyp, string> = {
  behandling: 'Behandling',
  protokollsida: 'Protokollsida',
  budgetforslag: 'Budgetförslag',
  arende: 'Ärende',
  ledamot: 'Ledamot',
  kallelsepunkt: 'Kallelsepunkt',
}

const fraga = (namn: string) =>
  computed<string>({
    get: () => (typeof route.query[namn] === 'string' ? (route.query[namn] as string) : ''),
    // Ett ändrat filter börjar om på första sidan.
    set: (v) => router.replace({ query: { ...route.query, [namn]: v || undefined, sida: undefined } }),
  })
const q = computed(() => (typeof route.query.q === 'string' ? route.query.q.trim() : ''))
const valtOrgan = fraga('organ')
const valtAr = fraga('ar')
const valdTyp = fraga('typ')
const sortering = fraga('sortering')
const sida = computed(() => Math.max(1, Number(route.query.sida) || 1))

const text = ref(q.value)
const organ = ref<Organ[]>([])
const svar = ref<Soksvar | null>(null)
const laddar = ref(false)
const fel = ref<string | null>(null)

async function ladda() {
  if (q.value.length < 2) {
    svar.value = null
    return
  }
  laddar.value = true
  fel.value = null
  try {
    svar.value = await sok({
      q: q.value,
      organ: valtOrgan.value,
      ar: valtAr.value,
      typ: (valdTyp.value || undefined) as Soktyp | undefined,
      sortering: (sortering.value || 'relevans') as Soksortering,
      sida: sida.value,
    })
  } catch (e) {
    if (e instanceof EjInloggad) return utloggad()
    svar.value = null
    fel.value = e instanceof ForManga || e instanceof Error ? e.message : String(e)
  } finally {
    laddar.value = false
  }
}

function sokNu() {
  const ny = text.value.trim()
  if (ny.length < 2) return
  router.push({ query: { ...route.query, q: ny, sida: undefined } })
}

function valjTyp(typ: Soktyp | '') {
  valdTyp.value = typ
}

function bladdra(steg: number) {
  router.push({ query: { ...route.query, sida: sida.value + steg > 1 ? String(sida.value + steg) : undefined } })
}

onMounted(async () => {
  try {
    organ.value = await hamtaOrgan()
  } catch (e) {
    if (e instanceof EjInloggad) return utloggad()
  }
})
watch(() => route.query, ladda, { immediate: true, deep: true })
watch(q, (v) => (text.value = v))

const totalt = computed(() => svar.value?.per_typ.reduce((s, p) => s + p.antal, 0) ?? 0)
const sidor = computed(() => (svar.value ? Math.max(1, Math.ceil(svar.value.antal / svar.value.sidstorlek)) : 1))
const arval = computed(() => svar.value?.ar_i_index ?? [])

const ar_ = (t: Soktraff) => t.datum?.slice(0, 4) ?? (t.ar ? String(t.ar) : null)
const meta = (t: Soktraff) =>
  [t.undertitel, t.organ?.namn, t.datum ? datum(t.datum) : t.typ === 'budgetforslag' && t.ar ? `Budgetår ${t.ar}` : null]
    .filter(Boolean)
    .join(' · ')
const pdftext = (t: Soktraff) => {
  const kalla = t.typ === 'kallelsepunkt' ? 'kallelsen' : t.typ === 'budgetforslag' ? 'förslaget' : 'protokollet'
  return t.sida ? `Sidan ${t.sida} i ${kalla}` : `Öppna ${kalla}`
}
const sammantrade = (t: Soktraff) => ({
  id: t.sammantrade_id ?? 0,
  organ: { id: t.organ?.id ?? '' },
  datum: t.datum,
  felaktigheter: t.felaktigheter,
})
</script>

<template>
  <section>
    <h1>Sök</h1>
    <form class="sokform" role="search" aria-label="Sök" @submit.prevent="sokNu">
      <label class="dold" for="sok-falt">Sökord</label>
      <input
        id="sok-falt"
        v-model="text"
        type="search"
        placeholder="Till exempel förskola, KS/2026-386 eller ett namn"
        data-testid="sokfalt"
      />
      <button type="submit" class="primar">Sök</button>
    </form>
    <p class="hjalp">
      Sökningen hittar protokollens text, behandlingar, ärenden, ledamöter, kallelser och budgetförslag och länkar
      till källorna. Ord böjs ("skolan" hittar "skolor"). Ett diarienummer ger ärendet först.
    </p>

    <template v-if="q.length >= 2">
      <div v-if="svar" class="typer" role="group" aria-label="Typ" data-testid="typfilter">
        <button type="button" :aria-pressed="!valdTyp" data-typ="" @click="valjTyp('')">
          Alla <span class="antal">{{ totalt }}</span>
        </button>
        <button
          v-for="p in svar.per_typ"
          :key="p.typ"
          type="button"
          :aria-pressed="valdTyp === p.typ"
          :data-typ="p.typ"
          :disabled="!p.antal && valdTyp !== p.typ"
          @click="valjTyp(p.typ)"
        >
          {{ TYPNAMN[p.typ] }} <span class="antal">{{ p.antal }}</span>
        </button>
      </div>

      <div class="filter" role="group" aria-label="Filter">
        <label>
          Organ
          <select v-model="valtOrgan" data-testid="filter-organ">
            <option value="">Alla organ</option>
            <option v-for="o in organ" :key="o.id" :value="o.id">{{ o.namn }}</option>
          </select>
        </label>
        <label>
          År
          <select v-model="valtAr" data-testid="filter-ar">
            <option value="">Alla år</option>
            <option v-if="valtAr && !arval.includes(Number(valtAr))" :value="valtAr">{{ valtAr }}</option>
            <option v-for="a in arval" :key="a" :value="String(a)">{{ a }}</option>
          </select>
        </label>
        <label>
          Sortering
          <select v-model="sortering" data-testid="sortering">
            <option value="">Relevans</option>
            <option value="datum">Senaste först</option>
          </select>
        </label>
      </div>

      <p v-if="fel" class="fel" role="alert">{{ fel }}</p>
      <p v-else-if="laddar && !svar" class="tom">Söker …</p>
      <template v-else-if="svar">
        <p class="sammanfattning" data-testid="antal-traffar" aria-live="polite">
          {{ svar.antal }} {{ svar.antal === 1 ? 'träff' : 'träffar' }} för ”{{ q }}”
        </p>
        <p v-if="!svar.antal" class="tom">Inga träffar. Pröva ett annat ord eller ta bort ett filter.</p>
        <ol class="traffar" :class="{ laddar }">
          <li v-for="t in svar.traffar" :key="`${t.typ}-${t.lank}-${t.sida}`" data-testid="traff" :data-typ="t.typ">
            <div class="rad1">
              <span class="typ">{{ ETIKETT[t.typ] }}</span>
              <span class="meta">{{ meta(t) }}</span>
            </div>
            <RouterLink :to="t.lank" class="rubrik" data-testid="traff-lank">{{ t.rubrik }}</RouterLink>
            <p v-if="t.utdrag.length" class="utdrag" data-testid="utdrag">
              <template v-for="(d, i) in t.utdrag" :key="i">
                <mark v-if="d.markerad">{{ d.text }}</mark>
                <template v-else>{{ d.text }}</template>
              </template>
            </p>
            <div class="rad3">
              <Tolkningsmarkering v-if="t.markeringar.includes('ocr')" ocr />
              <Tolkningsmarkering v-else-if="t.markeringar.includes('automatiskt_tolkad')" />
              <span v-if="t.markeringar.includes('rattad')" class="rattad" data-testid="rattad">
                <span aria-hidden="true">✎</span> Rättad av redaktionen
              </span>
              <span
                v-if="t.markeringar.includes('diarienummer_ur_kallelsen')"
                class="kallelse"
                data-testid="diarienummer-kallelse"
                title="Protokollet saknar diarienumret. Det står i kallelsen."
              >
                <span aria-hidden="true">↗</span> Diarienummer ur kallelsen
              </span>
              <Felaktighetsmarkering v-if="t.felaktigheter && t.sammantrade_id" :sammantrade="sammantrade(t)" />
              <a
                v-if="t.dokument"
                :href="t.dokument"
                target="_blank"
                rel="noopener"
                class="pdf"
                data-testid="traff-pdf"
                :title="ar_(t) ? `Källdokumentet (${ar_(t)})` : 'Källdokumentet'"
                >{{ pdftext(t) }}</a
              >
            </div>
          </li>
        </ol>
        <nav v-if="sidor > 1" class="bladdra" aria-label="Sidor">
          <button type="button" :disabled="sida <= 1" @click="bladdra(-1)">Föregående</button>
          <span>Sidan {{ sida }} av {{ sidor }}</span>
          <button type="button" :disabled="sida >= sidor" data-testid="nasta-sida" @click="bladdra(1)">Nästa</button>
        </nav>
      </template>
    </template>
  </section>
</template>

<style scoped>
h1 {
  font-size: 24px;
  font-weight: 600;
  margin: 0 0 16px;
}
.dold {
  position: absolute;
  width: 1px;
  height: 1px;
  overflow: hidden;
  clip: rect(0 0 0 0);
  white-space: nowrap;
}
.sokform {
  display: flex;
  gap: 8px;
  max-width: 720px;
}
.sokform input {
  flex: 1;
  min-width: 0;
  padding: 8px 12px;
  border: 1px solid var(--line-strong);
  border-radius: var(--radius);
  background: var(--surface);
  color: var(--ink);
  font: inherit;
}
.primar {
  padding: 8px 16px;
  border: 0;
  border-radius: var(--radius);
  background: var(--accent);
  color: var(--surface);
  font: inherit;
  font-weight: 600;
  cursor: pointer;
}
.hjalp {
  font-size: 12px;
  color: var(--ink-muted);
  margin: 8px 0 24px;
  max-width: 720px;
}
.typer {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-bottom: 16px;
}
.typer button {
  padding: 4px 12px;
  border: 1px solid var(--line-strong);
  border-radius: var(--radius);
  background: var(--surface);
  color: var(--ink-secondary);
  font: inherit;
  font-size: 13px;
  cursor: pointer;
}
.typer button[aria-pressed='true'] {
  background: var(--accent-wash);
  border-color: var(--accent);
  color: var(--accent);
  font-weight: 600;
}
.typer button:disabled {
  cursor: default;
  opacity: 0.6;
}
.antal {
  font-variant-numeric: tabular-nums;
  margin-left: 4px;
}
.filter {
  display: flex;
  gap: 16px;
  flex-wrap: wrap;
  margin-bottom: 16px;
}
.filter label {
  display: grid;
  gap: 4px;
  font-size: 13px;
  color: var(--ink-secondary);
}
.filter select {
  font: inherit;
  padding: 4px 8px;
  border: 1px solid var(--line-strong);
  border-radius: var(--radius);
  background: var(--surface);
  color: var(--ink);
}
.sammanfattning {
  font-size: 13px;
  color: var(--ink-secondary);
  margin: 0 0 8px;
}
.tom,
.fel {
  color: var(--ink-secondary);
}
.traffar {
  list-style: none;
  margin: 0;
  padding: 0;
  max-width: 900px;
}
.traffar.laddar {
  opacity: 0.6;
}
.traffar li {
  padding: 12px 0;
  border-bottom: 1px solid var(--line);
  display: grid;
  gap: 4px;
  min-width: 0;
}
.rad1 {
  display: flex;
  flex-wrap: wrap;
  gap: 4px 12px;
  font-size: 12px;
  color: var(--ink-muted);
}
.typ {
  font-weight: 600;
  color: var(--ink-secondary);
}
.rubrik {
  font-size: 15px;
  font-weight: 600;
  color: var(--accent);
  overflow-wrap: anywhere;
}
.utdrag {
  margin: 0;
  font-size: 13px;
  color: var(--ink-secondary);
  overflow-wrap: anywhere;
}
mark {
  background: var(--accent-wash);
  color: var(--ink);
  font-weight: 600;
  padding: 0 2px;
  border-radius: 2px;
}
.rad3 {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 8px;
  font-size: 12px;
}
.rattad,
.kallelse {
  display: inline-flex;
  gap: 4px;
  align-items: center;
  color: var(--ink-secondary);
  border: 1px solid var(--line-strong);
  border-radius: var(--radius);
  padding: 2px 8px;
}
.kallelse {
  border-style: dotted;
}
.pdf {
  color: var(--accent);
}
.bladdra {
  display: flex;
  gap: 12px;
  align-items: center;
  margin-top: 16px;
  font-size: 13px;
}
.bladdra button {
  padding: 4px 12px;
  border: 1px solid var(--line-strong);
  border-radius: var(--radius);
  background: var(--surface);
  color: var(--ink);
  font: inherit;
  cursor: pointer;
}
.bladdra button:disabled {
  cursor: default;
  opacity: 0.5;
}
@media (max-width: 720px) {
  .sokform {
    flex-direction: column;
  }
}
</style>
