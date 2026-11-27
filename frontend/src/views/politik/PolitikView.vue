<script setup lang="ts">
import { computed, inject, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import {
  EjInloggad,
  hamtaOrgan,
  hamtaSammantraden,
  sokBehandlingar,
  type Markningsid,
  type Organ,
  type Sammantradesrad,
  type Sokresultat,
} from '../../api'
import { sammantradesdatum } from '../../format'
import { organfarg } from '../../organ'
import Tolkningsmarkering from '../../components/Tolkningsmarkering.vue'
import Felaktighetsmarkering from '../../components/Felaktighetsmarkering.vue'
import Markningsfilter from '../../components/Markningsfilter.vue'

const route = useRoute()
const router = useRouter()
const utloggad = inject<() => void>('utloggad', () => {})

const organ = ref<Organ[]>([])
const sammantraden = ref<Sammantradesrad[]>([])
const laddar = ref(true)
const fel = ref<string | null>(null)

// Organ, år och söktext speglas i URL:en, så att en vy går att dela.
function fraga(namn: string) {
  return computed<string>({
    get: () => (typeof route.query[namn] === 'string' ? (route.query[namn] as string) : ''),
    set: (v) => router.replace({ query: { ...route.query, [namn]: v || undefined } }),
  })
}
const valtOrgan = fraga('organ')
const valtAr = fraga('ar')
// Märkningsfiltret (#195): bara sammanträden där någon paragraf har märkningen.
const valdMarkning = fraga('markning')
const sokning = fraga('q')
const soktext = ref(sokning.value)
const sokresultat = ref<Sokresultat | null>(null)

async function ladda() {
  laddar.value = true
  fel.value = null
  try {
    ;[organ.value, sammantraden.value] = await Promise.all([hamtaOrgan(), hamtaSammantraden(valtOrgan.value || undefined)])
  } catch (e) {
    if (e instanceof EjInloggad) return utloggad()
    fel.value = e instanceof Error ? e.message : String(e)
  } finally {
    laddar.value = false
  }
}
async function sok() {
  const q = sokning.value.trim()
  if (q.length < 2) {
    sokresultat.value = null
    return
  }
  try {
    sokresultat.value = await sokBehandlingar(q, valtOrgan.value || undefined, valtAr.value || undefined)
  } catch (e) {
    if (e instanceof EjInloggad) return utloggad()
    fel.value = e instanceof Error ? e.message : String(e)
  }
}
onMounted(() => Promise.all([ladda(), sok()]))
watch(valtOrgan, () => Promise.all([ladda(), sok()]))
watch(valtAr, sok)
watch(sokning, (q) => {
  soktext.value = q
  sok()
})
function skickaSokning() {
  sokning.value = soktext.value.trim()
}

// Åren som finns bland sammanträdena, för årsfiltret.
const ar = computed(() => [...new Set(sammantraden.value.map((s) => s.datum?.slice(0, 4)).filter(Boolean))] as string[])

const medMarkning = (s: Sammantradesrad, m: string) => !m || !!s.sammanstallning?.markningar[m as Markningsid]
const iAret = (s: Sammantradesrad) => !valtAr.value || (s.datum?.slice(0, 4) ?? 'Datum okänt') === valtAr.value
// Antal sammanträden per märkning, i valt organ och år.
const markningsantal = computed(() => {
  const antal: Partial<Record<Markningsid, number>> = {}
  for (const s of sammantraden.value.filter(iAret))
    for (const m of Object.keys(s.sammanstallning?.markningar ?? {}) as Markningsid[]) antal[m] = (antal[m] ?? 0) + 1
  return antal
})

// Sammanträdena grupperade per år, senaste först (API:t sorterar redan).
const perAr = computed(() => {
  const grupper = new Map<string, Sammantradesrad[]>()
  for (const s of sammantraden.value) {
    const ar = s.datum?.slice(0, 4) ?? 'Datum okänt'
    if (!iAret(s) || !medMarkning(s, valdMarkning.value)) continue
    grupper.set(ar, [...(grupper.get(ar) ?? []), s])
  }
  return [...grupper.entries()]
})

const tid = (s: Sammantradesrad) => (s.starttid ? `${s.starttid}${s.sluttid ? `–${s.sluttid}` : ''}` : '–')
const paragrafer = (s: Sammantradesrad) =>
  !s.paragrafer ? '–' : s.paragrafer[0] === s.paragrafer[1] ? `§ ${s.paragrafer[0]}` : `§§ ${s.paragrafer[0]}–${s.paragrafer[1]}`

// Den kompakta raden: "4 ärenden · 2 beslut · 1 förslag vidare". Förslag vidare bara när det finns.
const CHIPNAMN = { votering: 'Votering', reservation: 'Reservation', oenighet: 'Oenighet' }
function talen(s: Sammantradesrad) {
  const x = s.sammanstallning!
  return [
    { tal: x.arenden, text: x.arenden === 1 ? 'ärende' : 'ärenden' },
    { tal: x.beslut, text: 'beslut' },
    ...(x.forslag_vidare ? [{ tal: x.forslag_vidare, text: 'förslag vidare' }] : []),
  ]
}
</script>

<template>
  <header class="vyhuvud">
    <h1>Sammanträden</h1>
    <p class="ingress">
      Sammanträden i kommunens beslutande organ, med närvaro och de ärenden som behandlades. Uppgifterna är automatiskt
      lästa ur de justerade protokollen på harnosand.se. Protokoll som redaktionen har jämfört med tolkningen är
      märkta "Granskad". Varje uppgift länkar till protokollet.
    </p>
  </header>

  <div class="filter">
    <label>
      Organ
      <select v-model="valtOrgan" data-testid="organ">
        <option value="">Alla organ</option>
        <option v-for="o in organ" :key="o.id" :value="o.id">{{ o.namn }}</option>
      </select>
    </label>
    <label>
      År
      <select v-model="valtAr" data-testid="ar">
        <option value="">Alla år</option>
        <option v-for="a in ar" :key="a" :value="a">{{ a }}</option>
      </select>
    </label>
    <Markningsfilter v-model="valdMarkning" :antal="markningsantal" class="markning" />
    <form role="search" class="sok" @submit.prevent="skickaSokning">
      <label>
        Sök ärende
        <input
          v-model="soktext"
          type="search"
          placeholder="Rubrik eller diarienummer"
          data-testid="sok"
          @search="skickaSokning"
        />
      </label>
      <button type="submit">Sök</button>
    </form>
  </div>

  <section v-if="sokresultat" class="kort" aria-labelledby="sokrubrik" data-testid="sokresultat">
    <h2 id="sokrubrik">
      {{ sokresultat.antal === 1 ? '1 behandling' : `${sokresultat.antal} behandlingar` }} som matchar ”{{ sokning }}”
    </h2>
    <p v-if="sokresultat.antal > sokresultat.traffar.length" class="ingress">
      Visar de {{ sokresultat.traffar.length }} senaste. Välj organ eller år för att smalna av.
    </p>
    <p v-if="!sokresultat.antal" class="ingress">Inga behandlingar matchar sökningen.</p>
    <table v-else class="tabell">
      <thead>
        <tr>
          <th scope="col">Ärende</th>
          <th scope="col">Diarienummer</th>
          <th scope="col">Organ</th>
          <th scope="col">Sammanträde</th>
        </tr>
      </thead>
      <tbody>
        <tr
          v-for="t in sokresultat.traffar"
          :key="`${t.sammantrade.id}-${t.paragraf}`"
          data-testid="soktraff"
          :data-paragraf="t.paragraf"
        >
          <th scope="row">
            <RouterLink :to="`/politik/sammantraden/${t.sammantrade.id}/paragraf/${t.paragraf}`">
              § {{ t.paragraf }} {{ t.rubrik }}
            </RouterLink>
          </th>
          <td class="tal">
            {{ t.diarienummer.join(', ') || '–' }}
            <span v-if="t.diarienummer_ur_kallelsen" class="anteckning" data-testid="dnr-ur-kallelsen">ur kallelsen</span>
          </td>
          <td>{{ t.sammantrade.organ.namn }}</td>
          <td class="tal">{{ t.sammantrade.datum ?? '–' }}</td>
        </tr>
      </tbody>
    </table>
  </section>

  <p v-if="laddar">Hämtar uppgifter…</p>
  <p v-else-if="fel" class="fel">Kunde inte hämta uppgifter: {{ fel }}</p>
  <p v-else-if="!sammantraden.length" class="ingress">Inga protokoll har hämtats än.</p>

  <section v-for="[ar, rader] in perAr" v-else-if="!sokresultat" :key="ar" class="kort" :aria-labelledby="`ar-${ar}`">
    <h2 :id="`ar-${ar}`">{{ ar }}</h2>
    <table class="tabell" data-testid="sammantraden">
      <thead>
        <tr>
          <th scope="col">Sammanträde</th>
          <th scope="col">Organ</th>
          <th scope="col">Tid</th>
          <th scope="col">Paragrafer</th>
          <th scope="col">Sammanställning</th>
          <th scope="col">Underlag</th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="s in rader" :key="s.id" data-testid="sammantrade" :data-datum="s.datum">
          <th scope="row">
            <RouterLink :to="`/politik/sammantraden/${s.id}`">{{ sammantradesdatum(s.datum) }}</RouterLink>
          </th>
          <td>
            <span class="organ" :style="{ borderLeftColor: organfarg(s.organ.id) }" data-testid="organnamn">{{ s.organ.namn }}</span>
          </td>
          <td class="tal">{{ tid(s) }}</td>
          <td class="tal">{{ paragrafer(s) }}</td>
          <td data-testid="sammanstallning">
            <template v-if="s.sammanstallning">
              <span class="summa">
                <template v-for="(t, i) in talen(s)" :key="t.text"
                  ><span v-if="i" aria-hidden="true" class="punkt">·</span
                  ><span><span class="n">{{ t.tal }}</span> {{ t.text }}</span></template
                >
              </span>
              <span class="chips">
                <span
                  v-for="c in s.sammanstallning.chips"
                  :key="c.id"
                  class="chip"
                  :class="c.id"
                  :data-markning="c.id"
                  data-testid="chip"
                  >{{ CHIPNAMN[c.id] }}<template v-if="c.antal > 1"> · {{ c.antal }}</template></span
                >
                <span v-if="s.sammanstallning.enigt" class="enigt" data-testid="enigt">Enigt</span>
              </span>
            </template>
            <span v-else class="streck" data-testid="ingen-sammanstallning" title="Protokollet kunde inte tolkas automatiskt">–</span>
          </td>
          <td>
            <span class="underlag">
              <Tolkningsmarkering :ej-tolkad="s.tolkning === 'ej_tolkad'" :ocr="s.ocr" :granskad="s.granskad" kort />
              <Felaktighetsmarkering :sammantrade="s" />
            </span>
          </td>
        </tr>
      </tbody>
    </table>
  </section>
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
  flex-wrap: wrap;
  gap: 16px;
  margin-bottom: 24px;
  font-size: 13px;
}
.filter label {
  display: flex;
  align-items: center;
  gap: 8px;
  color: var(--ink-secondary);
}
.sok {
  display: flex;
  gap: 8px;
  align-items: center;
}
.filter input,
.filter button {
  font: inherit;
  padding: 4px 8px;
  border: 1px solid var(--line-strong);
  border-radius: var(--radius);
  background: var(--surface-raised);
  color: var(--ink);
}
.filter input {
  width: 22ch;
}
.filter button {
  cursor: pointer;
}
.filter select {
  font: inherit;
  padding: 4px 8px;
  border: 1px solid var(--line-strong);
  border-radius: var(--radius);
  background: var(--surface-raised);
  color: var(--ink);
}
.kort {
  background: var(--surface);
  border: 1px solid var(--line);
  border-radius: var(--radius);
  padding: 24px;
  margin-bottom: 24px;
  overflow-x: auto;
}
.kort h2 {
  margin-bottom: 12px;
}
.tabell {
  border-collapse: collapse;
  font-size: 13px;
  width: 100%;
}
.tabell th,
.tabell td {
  padding: 6px 16px 6px 0;
  border-bottom: 1px solid var(--line);
  text-align: left;
  vertical-align: top;
}
.tabell thead th {
  color: var(--ink-secondary);
  font-weight: 600;
  white-space: nowrap;
}
.tabell tbody th {
  font-weight: 600;
}
.tabell tbody th a::first-letter {
  text-transform: uppercase;
}
.hoger {
  text-align: right !important;
}
.fel {
  color: var(--status-critical);
}
.filter .markning {
  display: flex;
  align-items: center;
  gap: 8px;
}
.organ {
  display: inline-block;
  padding-left: 8px;
  border-left: 4px solid var(--ink-muted);
  white-space: nowrap;
}
.summa {
  display: flex;
  flex-wrap: wrap;
  gap: 2px 6px;
  color: var(--ink-secondary);
}
.summa .n {
  font-weight: 600;
  color: var(--ink);
}
.chips {
  display: flex;
  flex-wrap: wrap;
  gap: 4px;
  margin-top: 4px;
}
.chip {
  padding: 0 6px;
  font-size: 11px;
  font-weight: 500;
  line-height: 18px;
  white-space: nowrap;
  border-radius: var(--radius-mark);
}
.chip.votering {
  background: var(--markning-votering);
  color: var(--markning-votering-text);
}
.chip.reservation {
  background: var(--markning-reservation);
  color: var(--markning-reservation-text);
}
.chip.oenighet {
  background: var(--markning-oenighet);
  color: var(--markning-oenighet-text);
}
.enigt,
.streck {
  font-size: 12px;
  color: var(--ink-muted);
}
td .underlag {
  display: inline-flex;
  flex-wrap: wrap;
  gap: 6px;
  align-items: baseline;
}
</style>
