<script setup lang="ts">
import { computed, inject, ref, watch, type Ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import {
  delaUppLedamot,
  EjInloggad,
  hamtaLedamot,
  hamtaLedamoter,
  Saknas,
  slaIhopLedamoter,
  type Jag,
  type Ledamot,
  type Ledamotsrad,
} from '../../api'
import { paragraftext, sammantradesdatum } from '../../format'
import Partimarkering from '../../components/Partimarkering.vue'
import PolitikFlikar from '../../components/PolitikFlikar.vue'
import Tolkningsmarkering from '../../components/Tolkningsmarkering.vue'

const route = useRoute()
const router = useRouter()
const utloggad = inject<() => void>('utloggad', () => {})
const jag = inject<Ref<Jag | null>>('jag', ref(null))
const arRedaktor = computed(() => jag.value?.roller.includes('redaktor') ?? false)

const l = ref<Ledamot | null>(null)
const laddar = ref(true)
const fel = ref<string | null>(null)

function visa(ny: Ledamot) {
  l.value = ny
  // Ett sammanslaget namn visas under personens adress.
  if (String(ny.id) !== String(route.params.id)) router.replace(`/politik/ledamoter/${ny.id}`)
}

async function ladda() {
  laddar.value = true
  fel.value = null
  try {
    visa(await hamtaLedamot(String(route.params.id)))
  } catch (e) {
    if (e instanceof EjInloggad) return utloggad()
    fel.value = e instanceof Saknas ? 'Ledamoten finns inte.' : e instanceof Error ? e.message : String(e)
  } finally {
    laddar.value = false
  }
}
watch(
  () => route.params.id,
  (id) => {
    if (!l.value || String(l.value.id) !== String(id)) ladda()
  },
  { immediate: true },
)

const KATEGORI = { beslutande: 'Beslutande', ej_tjanstgorande: 'Närvarande ersättare', franvarande: 'Frånvarande' }

function period(fran: string | null, till: string | null) {
  if (!fran) return '–'
  return fran === till ? fran : `${fran} – ${till}`
}

// Redaktör: slå ihop och dela upp.
const register = ref<Ledamotsrad[]>([])
const sokAnnan = ref('')
const meddelande = ref<string | null>(null)
const skrivfel = ref<string | null>(null)
const arbetar = ref(false)
const forslag = computed(() => {
  const q = sokAnnan.value.trim().toLocaleLowerCase('sv')
  if (q.length < 2 || !l.value) return []
  return register.value
    .filter((r) => r.id !== l.value!.id && [r.namn, ...r.andra_namn].some((n) => n.toLocaleLowerCase('sv').includes(q)))
    .slice(0, 8)
})
watch(arRedaktor, async (ja) => {
  if (ja && !register.value.length) register.value = await hamtaLedamoter()
}, { immediate: true })

async function skriv(atgard: () => Promise<Ledamot>, klart: (ny: Ledamot) => string) {
  arbetar.value = true
  skrivfel.value = meddelande.value = null
  try {
    const ny = await atgard()
    visa(ny)
    meddelande.value = klart(ny)
    sokAnnan.value = ''
    register.value = await hamtaLedamoter()
  } catch (e) {
    if (e instanceof EjInloggad) return utloggad()
    skrivfel.value = e instanceof Error ? e.message : String(e)
  } finally {
    arbetar.value = false
  }
}
const slaIhop = (annan: Ledamotsrad) =>
  skriv(() => slaIhopLedamoter(l.value!.id, annan.id), (ny) => `${annan.namn} är nu sammanslagen med ${ny.namn}.`)
const delaUpp = (namn: { id: number; namn: string }) =>
  skriv(
    async () => {
      await delaUppLedamot(namn.id)
      return hamtaLedamot(l.value!.id)
    },
    () => `${namn.namn} är nu en egen person igen.`,
  )
</script>

<template>
  <nav class="brodsmulor" aria-label="Brödsmulor">
    <RouterLink to="/politik">Politik och beslut</RouterLink>
    <span aria-hidden="true">›</span>
    <RouterLink to="/politik/ledamoter">Ledamöter</RouterLink>
    <span aria-hidden="true">›</span>
    <span>{{ l?.namn ?? 'Ledamot' }}</span>
  </nav>

  <p v-if="laddar">Hämtar uppgifter…</p>
  <p v-else-if="fel" class="fel">{{ fel }}</p>

  <template v-else-if="l">
    <header class="vyhuvud">
      <h1>{{ l.namn }}</h1>
      <p v-if="l.namn_varianter.length > 1" class="ingress" data-testid="andra-namn">
        Skrivs även
        {{ l.namn_varianter.filter((n) => !n.huvudnamn).map((n) => n.namn).join(', ') }} i protokollen.
      </p>
      <p class="markering"><Tolkningsmarkering :ej-tolkad="false" /></p>
    </header>
    <PolitikFlikar />

    <section class="kort" aria-labelledby="parti-rubrik">
      <h2 id="parti-rubrik">Parti över tid</h2>
      <p class="ingress">Som protokollen anger det vid varje sammanträde. Inget parti fylls i från andra källor.</p>
      <table class="tabell" data-testid="partier">
        <thead>
          <tr>
            <th scope="col">Parti</th>
            <th scope="col">Period</th>
            <th scope="col" class="hoger">Sammanträden</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="(p, i) in [...l.partier_over_tid].reverse()" :key="i" data-testid="partiperiod">
            <td><Partimarkering :parti="p.parti" /></td>
            <td class="tal">{{ period(p.fran, p.till) }}</td>
            <td class="tal hoger">{{ p.antal }}</td>
          </tr>
        </tbody>
      </table>
    </section>

    <section class="kort" aria-labelledby="organ-rubrik">
      <h2 id="organ-rubrik">Organ, roller och närvaro</h2>
      <p class="ingress">
        Räknat ur närvarolistorna. Frånvaro syns bara när protokollet redovisar den, vilket fullmäktiges tabeller gör.
      </p>
      <table class="tabell" data-testid="organ-tabell">
        <thead>
          <tr>
            <th scope="col">Organ</th>
            <th scope="col">Roller</th>
            <th scope="col">Period</th>
            <th scope="col" class="hoger">Beslutande</th>
            <th scope="col" class="hoger">Närvarande ersättare</th>
            <th scope="col" class="hoger">Frånvarande</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="o in l.organ" :key="o.organ.id" data-testid="organrad" :data-organ="o.organ.id">
            <th scope="row">{{ o.organ.namn }}</th>
            <td>{{ o.roller.join(', ') || '–' }}</td>
            <td class="tal">{{ period(o.fran, o.till) }}</td>
            <td class="tal hoger">{{ o.beslutande }}</td>
            <td class="tal hoger">{{ o.ej_tjanstgorande }}</td>
            <td class="tal hoger">{{ o.franvarande }}</td>
          </tr>
        </tbody>
      </table>
    </section>

    <section class="kort" aria-labelledby="sam-rubrik">
      <h2 id="sam-rubrik">Sammanträden <span class="antal">({{ l.sammantraden.length }})</span></h2>
      <table class="tabell" data-testid="ledamotens-sammantraden">
        <thead>
          <tr>
            <th scope="col">Sammanträde</th>
            <th scope="col">Organ</th>
            <th scope="col">Parti</th>
            <th scope="col">Roll</th>
            <th scope="col">Närvaro</th>
          </tr>
        </thead>
        <tbody>
          <tr
            v-for="s in l.sammantraden"
            :key="s.sammantrade.id + s.namn"
            data-testid="ledamotens-sammantrade"
            :data-datum="s.sammantrade.datum"
          >
            <th scope="row">
              <RouterLink :to="`/politik/sammantraden/${s.sammantrade.id}`" class="forsta-versal">
                {{ sammantradesdatum(s.sammantrade.datum) }}
              </RouterLink>
            </th>
            <td>{{ s.sammantrade.organ.namn }}</td>
            <td><Partimarkering :parti="s.parti" /></td>
            <td>{{ s.roll ?? '–' }}</td>
            <td>
              {{ KATEGORI[s.kategori] }}
              <span v-if="s.tjanstgor_for" class="anteckning">
                · tjänstgör för {{ s.tjanstgor_for.namn }}
              </span>
              <span v-if="s.paragrafer" class="anteckning"> · vid {{ paragraftext(s.paragrafer) }}</span>
              <span v-if="s.jav.length" class="anteckning"> · jäv {{ paragraftext(s.jav) }}</span>
            </td>
          </tr>
        </tbody>
      </table>
    </section>

    <section v-if="arRedaktor" class="kort redaktor" aria-labelledby="red-rubrik" data-testid="redaktor">
      <h2 id="red-rubrik">Redaktör: samma person under flera namn</h2>
      <p class="ingress">
        Registret identifierar personer på namn. Slå ihop när samma person skrivs olika i protokollen, och dela upp om
        det blev fel. Personen visas under namnet på den här sidan.
      </p>
      <p v-if="meddelande" class="meddelande" role="status" data-testid="meddelande">{{ meddelande }}</p>
      <p v-if="skrivfel" class="fel" role="alert">{{ skrivfel }}</p>

      <ul v-if="l.namn_varianter.length > 1" class="namnlista">
        <li v-for="n in l.namn_varianter" :key="n.id" data-testid="namnvariant">
          {{ n.namn }} <span class="anteckning">({{ n.antal }} i närvarolistor)</span>
          <span v-if="n.huvudnamn" class="anteckning">· huvudnamn</span>
          <button v-else type="button" :disabled="arbetar" data-testid="dela-upp" @click="delaUpp(n)">Dela upp</button>
        </li>
      </ul>

      <label class="sokfalt">
        Slå ihop med
        <input v-model="sokAnnan" type="search" placeholder="Sök annat namn" data-testid="sok-annan" />
      </label>
      <ul v-if="forslag.length" class="namnlista">
        <li v-for="f in forslag" :key="f.id" data-testid="forslag">
          {{ f.namn }} <Partimarkering :parti="f.parti" />
          <span class="anteckning">· {{ f.organ.map((o) => o.namn).join(', ') }} · {{ f.antal_sammantraden }} sammanträden</span>
          <button type="button" :disabled="arbetar" data-testid="sla-ihop" @click="slaIhop(f)">Slå ihop</button>
        </li>
      </ul>
    </section>
  </template>
</template>

<style scoped>
.brodsmulor {
  display: flex;
  gap: 8px;
  font-size: 13px;
  color: var(--ink-muted);
  margin-bottom: 12px;
}
.brodsmulor a {
  color: var(--accent);
}
.vyhuvud {
  margin-bottom: 16px;
}
.ingress {
  color: var(--ink-secondary);
  margin: 0 0 12px;
  max-width: 70ch;
}
.markering {
  margin: 12px 0 0;
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
.antal {
  color: var(--ink-muted);
  font-weight: 400;
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
.forsta-versal {
  display: inline-block;
}
.forsta-versal::first-letter {
  text-transform: uppercase;
}
.anteckning {
  color: var(--ink-muted);
}
.hoger {
  text-align: right !important;
}
.namnlista {
  list-style: none;
  margin: 0 0 16px;
  padding: 0;
  font-size: 13px;
}
.namnlista li {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 6px 0;
  border-bottom: 1px solid var(--line);
}
.sokfalt {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 13px;
  color: var(--ink-secondary);
  margin-bottom: 8px;
}
input,
button {
  font: inherit;
  padding: 4px 8px;
  border: 1px solid var(--line-strong);
  border-radius: var(--radius);
  background: var(--surface-raised);
  color: var(--ink);
}
button {
  cursor: pointer;
}
.meddelande {
  color: var(--status-good);
  font-size: 13px;
}
.fel {
  color: var(--status-critical);
}
</style>
