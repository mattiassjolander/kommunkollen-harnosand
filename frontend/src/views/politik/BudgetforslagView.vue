<script setup lang="ts">
// Partiernas budgetförslag (#48): förslagen för ett budgetår bredvid varandra och bredvid den
// antagna budgeten. Budgetår och visat år speglas i URL:en (design.md, Filter). Varje siffra
// länkar till sidan i originalet. Partier står i alfabetisk ordning (design.md).
import { computed, inject, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import {
  EjInloggad,
  hamtaBudget,
  hamtaBudgetar,
  type Budgetforslag,
  type Budgetjamforelse,
  type Differens,
} from '../../api'
import { tal, talforandring } from '../../format'
import Partimarkering from '../../components/Partimarkering.vue'
import PolitikFlikar from '../../components/PolitikFlikar.vue'

const route = useRoute()
const router = useRouter()
const utloggad = inject<() => void>('utloggad', () => {})

const ar = ref<{ budgetar: number; forslag: number; antagen: boolean }[]>([])
const j = ref<Budgetjamforelse | null>(null)
const laddar = ref(true)
const fel = ref<string | null>(null)

const valtAr = computed<number | null>({
  get: () => (typeof route.query.ar === 'string' ? Number(route.query.ar) : (ar.value[0]?.budgetar ?? null)),
  set: (v) => router.replace({ query: { ...route.query, ar: v ? String(v) : undefined, visa: undefined } }),
})
const visa = computed<number | null>({
  get: () => (typeof route.query.visa === 'string' ? Number(route.query.visa) : valtAr.value),
  set: (v) => router.replace({ query: { ...route.query, visa: v && v !== valtAr.value ? String(v) : undefined } }),
})

async function ladda() {
  if (!valtAr.value) return
  laddar.value = true
  fel.value = null
  try {
    j.value = await hamtaBudget(valtAr.value)
  } catch (e) {
    if (e instanceof EjInloggad) return utloggad()
    fel.value = e instanceof Error ? e.message : String(e)
  } finally {
    laddar.value = false
  }
}
onMounted(async () => {
  try {
    ar.value = await hamtaBudgetar()
  } catch (e) {
    if (e instanceof EjInloggad) return utloggad()
    fel.value = e instanceof Error ? e.message : String(e)
  }
  if (!ar.value.length) laddar.value = false
  await ladda()
})
watch(valtAr, ladda)

const forslag = computed(() => j.value?.forslag ?? [])
const antagen = computed(() => forslag.value.find((f) => f.id === j.value?.antagen) ?? null)
// Länk till sidan i originalet. Ett Word-dokument har inga fasta sidor, så där blir siffran ingen länk.
const lank = (f: Budgetforslag, s?: number) =>
  s ? { href: `${f.original}#page=${s}`, target: '_blank', rel: 'noopener', title: `Sidan ${s}` } : {}

function skatt(f: Budgetforslag) {
  return f.uppgifter.skattesats
}
function resultat(f: Budgetforslag) {
  return f.uppgifter.resultat.find((r) => r.ar === visa.value) ?? null
}
function ram(f: Budgetforslag, organ: string) {
  return f.uppgifter.ramar.find((r) => r.organ === organ && r.ar === visa.value) ?? null
}
function diffResultat(f: Budgetforslag): Differens | null {
  return f.differens?.resultat.find((d) => d.ar === visa.value) ?? null
}
function diffRam(f: Budgetforslag, organ: string): Differens | null {
  return f.differens?.ramar.find((d) => d.organ === organ && d.ar === visa.value) ?? null
}
function difftext(d: Differens): string {
  return d.procent === null ? talforandring(d.mnkr, 'mnkr') : `${talforandring(d.mnkr, 'mnkr')} (${talforandring(d.procent, '%')})`
}
const tvadecimaler = new Intl.NumberFormat('sv-SE', { minimumFractionDigits: 2, maximumFractionDigits: 2 })
const skattesats = (v: number) => `${tvadecimaler.format(v)} %`
const pe = (v: number) => (v === 0 ? 'Oförändrad' : `${v > 0 ? '+' : '−'}${tvadecimaler.format(Math.abs(v))} procentenheter`)
</script>

<template>
  <header class="vyhuvud">
    <h1>Politik och beslut</h1>
    <p class="ingress">
      Partiernas budgetförslag till kommunfullmäktige, i samma budgetmodell som den antagna budgeten: skattesats,
      budgeterat resultat och ram per nämnd. Siffrorna är de som står i förslagen, med länk till sidan i originalet.
    </p>
  </header>
  <PolitikFlikar />

  <p v-if="fel" class="fel" role="alert">{{ fel }}</p>
  <p v-else-if="!laddar && !ar.length" class="saknas" data-testid="inga-budgetar">Inga budgetförslag är publicerade än.</p>
  <template v-else>
    <div class="filter" role="group" aria-label="Filter">
      <label>
        Budgetår
        <select v-model.number="valtAr" data-testid="filter-budgetar">
          <option v-for="a in ar" :key="a.budgetar" :value="a.budgetar">{{ a.budgetar }}</option>
        </select>
      </label>
      <label v-if="j && j.ar.length > 1">
        Visa år
        <select v-model.number="visa" data-testid="filter-visa">
          <option v-for="a in j.ar" :key="a" :value="a">{{ a === j.budgetar ? `${a} (budgetår)` : a > j.budgetar ? `${a} (plan)` : a }}</option>
        </select>
      </label>
    </div>

    <p v-if="laddar && !j">Hämtar budgetförslag…</p>
    <section v-else-if="j" class="kort" aria-labelledby="jamforelse-rubrik">
      <h2 id="jamforelse-rubrik">Budgetförslag {{ j.budgetar }}<template v-if="visa !== j.budgetar">, {{ visa }}</template></h2>
      <p v-if="antagen" class="forklaring">
        Skillnaden mot den antagna budgeten visas under varje belopp, när förslaget anger ett belopp för samma nämnd och
        år. Förslag som bara anger förändringar visas med förändringen och vad den räknas från.
      </p>
      <p v-else class="forklaring" data-testid="ingen-antagen">
        Den antagna budgeten för {{ j.budgetar }} finns inte här än, så ingen skillnad räknas.
      </p>

      <div class="rulla">
        <table class="tabell" data-testid="budgetjamforelse">
          <thead>
            <tr>
              <th scope="col">Mnkr</th>
              <th v-for="f in j.forslag" :key="f.id" scope="col" class="forslag" :data-nyckel="f.nyckel">
                <span class="partier">
                  <Partimarkering v-for="p in f.partier" :key="p" :parti="p" />
                </span>
                <span class="titel">{{ f.titel }}</span>
                <span v-if="f.antagen" class="antagen" data-testid="antagen">Antagen budget</span>
                <span v-if="f.typ === 'tillagg'" class="antagen">Tilläggsbudget</span>
                <a :href="f.original" class="original" rel="noopener" target="_blank">Originalet</a>
              </th>
            </tr>
          </thead>
          <tbody>
            <tr data-rad="skattesats">
              <th scope="row">Skattesats</th>
              <td v-for="f in j.forslag" :key="f.id" class="num">
                <template v-if="skatt(f)">
                  <component :is="skatt(f)!.sida ? 'a' : 'span'" v-bind="lank(f, skatt(f)!.sida)">
                    <template v-if="skatt(f)!.procent !== undefined">{{ skattesats(skatt(f)!.procent!) }}</template>
                    <template v-else>{{ pe(skatt(f)!.forandring!) }}</template>
                  </component>
                  <span v-if="f.differens?.skattesats" class="diff">{{ pe(f.differens.skattesats) }}</span>
                  <span v-else-if="skatt(f)!.procent !== undefined && skatt(f)!.forandring !== undefined" class="diff">{{ pe(skatt(f)!.forandring!) }}</span>
                </template>
                <span v-else class="saknas">Anges inte</span>
              </td>
            </tr>
            <tr data-rad="resultat">
              <th scope="row">Budgeterat resultat</th>
              <td v-for="f in j.forslag" :key="f.id" class="num">
                <template v-if="resultat(f)">
                  <component :is="resultat(f)!.sida ? 'a' : 'span'" v-bind="lank(f, resultat(f)!.sida)">
                    <template v-if="resultat(f)!.mnkr !== undefined">{{ tal(resultat(f)!.mnkr!, 'mnkr') }}</template>
                    <template v-if="resultat(f)!.procent !== undefined">
                      <template v-if="resultat(f)!.mnkr !== undefined">, </template>{{ tal(resultat(f)!.procent!, '%') }}
                    </template>
                  </component>
                  <span v-if="diffResultat(f)" class="diff">{{ difftext(diffResultat(f)!) }}</span>
                </template>
                <span v-else class="saknas">Anges inte</span>
              </td>
            </tr>
            <tr v-for="o in j.organ" :key="o" :data-organ="o">
              <th scope="row">{{ o }}</th>
              <td v-for="f in j.forslag" :key="f.id" class="num">
                <template v-if="ram(f, o)">
                  <component :is="ram(f, o)!.sida ? 'a' : 'span'" v-bind="lank(f, ram(f, o)!.sida)">
                    <template v-if="ram(f, o)!.mnkr !== undefined">{{ tal(ram(f, o)!.mnkr!, 'mnkr') }}</template>
                    <template v-else>{{ talforandring(ram(f, o)!.forandring!, 'mnkr') }}</template>
                  </component>
                  <span v-if="diffRam(f, o)" class="diff" data-testid="differens">{{ difftext(diffRam(f, o)!) }}</span>
                  <span v-else-if="ram(f, o)!.mnkr === undefined" class="diff">mot {{ f.uppgifter.utgangslage ?? 'utgångsläget' }}</span>
                </template>
                <span v-else class="saknas">Anges inte</span>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
      <ul v-if="j.forslag.some((f) => f.anmarkning || f.uppgifter.utgangslage)" class="anmarkningar">
        <li v-for="f in j.forslag.filter((f) => f.anmarkning || f.uppgifter.utgangslage)" :key="f.id">
          <strong>{{ f.titel }}:</strong>
          <template v-if="f.uppgifter.utgangslage"> förändringarna räknas från {{ f.uppgifter.utgangslage }}.</template>
          {{ f.anmarkning }}
        </li>
      </ul>
      <p class="kallrad">Ramarna är nämndernas nettokostnad eller tilldelade skattemedel, som förslaget redovisar dem.</p>
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
.filter label {
  display: grid;
  gap: 4px;
  font-size: 13px;
  color: var(--ink-secondary);
}
.filter select {
  font: inherit;
  font-size: 14px;
  color: var(--ink);
  background: var(--surface);
  border: 1px solid var(--line);
  border-radius: var(--radius);
  padding: 6px 8px;
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
.forklaring {
  font-size: 13px;
  color: var(--ink-secondary);
  max-width: 70ch;
  margin: 0 0 12px;
}
.rulla {
  overflow-x: auto;
}
.tabell {
  border-collapse: collapse;
  width: 100%;
  font-size: 13px;
}
.tabell th,
.tabell td {
  text-align: left;
  padding: 8px;
  border-bottom: 1px solid var(--line);
  vertical-align: top;
}
.tabell thead th {
  font-weight: 600;
  min-width: 130px;
}
.tabell tbody th {
  white-space: nowrap;
  font-weight: 600;
}
.tabell .num {
  text-align: right;
  font-variant-numeric: tabular-nums;
  white-space: nowrap;
}
.forslag {
  text-align: right !important;
}
.forslag > span,
.forslag > a {
  display: block;
}
.partier {
  display: flex !important;
  gap: 8px;
  justify-content: flex-end;
  flex-wrap: wrap;
}
.titel {
  font-weight: 400;
  color: var(--ink-secondary);
  white-space: normal;
}
.antagen {
  font-size: 12px;
  font-weight: 400;
  color: var(--ink-secondary);
}
.original {
  font-size: 12px;
  font-weight: 400;
}
.diff {
  display: block;
  font-size: 12px;
  color: var(--ink-secondary);
}
.saknas {
  color: var(--ink-muted);
  font-style: italic;
}
.anmarkningar {
  font-size: 13px;
  color: var(--ink-secondary);
  margin: 12px 0 0;
  padding-left: 18px;
}
.kallrad {
  font-size: 12px;
  color: var(--ink-muted);
  margin: 8px 0 0;
}
.fel {
  color: var(--status-critical);
}
a {
  color: var(--accent);
}
</style>
