<script setup lang="ts">
import { computed, inject, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { EjInloggad, hamtaStyrandeDokument, type Styrdokumentlista, type Styrdokumentrad } from '../../api'
import { datum } from '../../format'
import Giltighetsmarkering from '../../components/Giltighetsmarkering.vue'

// Kommunens styrande dokument (#63): alla PDF:er på kommunens sida, med kategori, vem som fastställt dem och
// giltighet. Uppgifterna är lästa ur dokumenten och återges som de står.

const route = useRoute()
const router = useRouter()
const utloggad = inject<() => void>('utloggad', () => {})

const data = ref<Styrdokumentlista | null>(null)
const laddar = ref(true)
const fel = ref<string | null>(null)

// Filtren speglas i URL:en, så att ett urval går att dela. Giltigheten är "gällande" om inget annat valts.
function fraga(namn: string, standard = '') {
  return computed<string>({
    get: () => (typeof route.query[namn] === 'string' ? (route.query[namn] as string) : standard),
    set: (v) => router.replace({ query: { ...route.query, [namn]: v === standard ? undefined : v || 'alla' } }),
  })
}
const sok = fraga('q')
const valdKategori = fraga('kategori')
const valtFaststallt = fraga('faststallt')
const valdGiltighet = fraga('giltighet', 'gallande')

onMounted(async () => {
  try {
    data.value = await hamtaStyrandeDokument()
  } catch (e) {
    if (e instanceof EjInloggad) return utloggad()
    fel.value = e instanceof Error ? e.message : String(e)
  } finally {
    laddar.value = false
  }
})

/** Nyckeln för filtret "Fastställt av": organet, annars texten som den står, annars "saknas". */
const faststalltNyckel = (d: Styrdokumentrad) => d.faststallt.organ?.id ?? d.faststallt.text ?? 'saknas'
const faststalltNamn = (d: Styrdokumentrad) => d.faststallt.organ?.namn ?? d.faststallt.text ?? 'Uppgift saknas'

// Plattformens organ först, sedan det som står i övriga dokument i bokstavsordning, och "Uppgift saknas" sist.
const faststalltVal = computed(() => {
  const val = new Map<string, { namn: string; vikt: number }>()
  for (const d of data.value?.dokument ?? [])
    val.set(faststalltNyckel(d), { namn: faststalltNamn(d), vikt: d.faststallt.organ ? 0 : d.faststallt.text ? 1 : 2 })
  return [...val.entries()]
    .sort(([, a], [, b]) => a.vikt - b.vikt || a.namn.localeCompare(b.namn, 'sv'))
    .map(([nyckel, { namn }]) => ({ nyckel, namn }))
})

const urval = computed(() => {
  const q = sok.value.trim().toLocaleLowerCase('sv')
  return (data.value?.dokument ?? []).filter(
    (d) =>
      (!q || d.titel.toLocaleLowerCase('sv').includes(q)) &&
      (!valdKategori.value || d.kategorier.includes(valdKategori.value)) &&
      (!valtFaststallt.value || faststalltNyckel(d) === valtFaststallt.value) &&
      (valdGiltighet.value === 'alla' || d.giltighet.status === valdGiltighet.value),
  )
})

const antal = (status: string) => (data.value?.dokument ?? []).filter((d) => d.giltighet.status === status).length
</script>

<template>
  <header class="vyhuvud">
    <h1>Styrande dokument</h1>
    <p class="ingress">
      De dokument som kommunen publicerar på sidan Kommunens styrande dokument: reglementen, delegationsordningar,
      policyer, planer, program, riktlinjer och föreskrifter. Kategorin är rubriken på kommunens sida. Vem som
      fastställt dokumentet och giltigheten är lästa ur dokumenten och återges som de står där.
    </p>
    <p class="ingress">
      <RouterLink to="/politik/styrande-dokument/motstridigheter" data-testid="till-motstridigheter">Motstridigheter</RouterLink>:
      ställen i reglementen och delegationsordningar som inte går ihop, enligt redaktionens analys.
      <RouterLink to="/politik/styrande-dokument/processer" data-testid="till-processer">Processer</RouterLink>: hur
      saker ska gå till enligt dokumenten, steg för steg.
    </p>
  </header>

  <div class="filter">
    <label>
      Sök titel
      <input v-model="sok" type="search" placeholder="Titel" data-testid="sok-titel" />
    </label>
    <label>
      Kategori
      <select v-model="valdKategori" data-testid="kategori">
        <option value="">Alla kategorier</option>
        <option v-for="k in data?.kategorier ?? []" :key="k" :value="k">{{ k }}</option>
      </select>
    </label>
    <label>
      Fastställt av
      <select v-model="valtFaststallt" data-testid="faststallt">
        <option value="">Alla</option>
        <option v-for="f in faststalltVal" :key="f.nyckel" :value="f.nyckel">{{ f.namn }}</option>
      </select>
    </label>
    <label>
      Giltighet
      <select v-model="valdGiltighet" data-testid="giltighet">
        <option value="gallande">Gällande ({{ antal('gallande') }})</option>
        <option value="utganget">Utgångna ({{ antal('utganget') }})</option>
        <option value="borttaget">Borttagna ({{ antal('borttaget') }})</option>
        <option value="alla">Alla</option>
      </select>
    </label>
  </div>

  <p v-if="laddar">Hämtar uppgifter…</p>
  <p v-else-if="fel" class="fel">Kunde inte hämta uppgifter: {{ fel }}</p>
  <p v-else-if="!data?.dokument.length" class="ingress">Inga styrande dokument har hämtats än.</p>
  <section v-else class="kort" aria-labelledby="dok-rubrik">
    <h2 id="dok-rubrik">{{ urval.length === 1 ? '1 dokument' : `${urval.length} dokument` }}</h2>
    <p v-if="!urval.length" class="ingress">Inget dokument matchar urvalet.</p>
    <table v-else class="tabell" data-testid="styrande-dokument">
      <thead>
        <tr>
          <th scope="col">Dokument</th>
          <th scope="col">Kategori</th>
          <th scope="col">Fastställt av</th>
          <th scope="col">Giltighet</th>
          <th scope="col">Motstridigheter</th>
          <th scope="col">Processer</th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="d in urval" :key="d.id" data-testid="styrdokument" :data-id="d.id">
          <th scope="row">
            <RouterLink :to="`/politik/styrande-dokument/${d.id}`">{{ d.titel }}</RouterLink>
          </th>
          <td>{{ d.kategorier.join(', ') }}</td>
          <td>
            <template v-if="d.faststallt.text">
              {{ faststalltNamn(d) }}<span v-if="d.faststallt.datum" class="tal">, {{ datum(d.faststallt.datum) }}</span>
            </template>
            <span v-else class="saknas">Uppgift saknas</span>
          </td>
          <td><Giltighetsmarkering :giltighet="d.giltighet" /></td>
          <td class="tal" data-testid="antal-motstridigheter">
            <template v-if="d.motstridigheter">{{ d.motstridigheter }} <span class="analysetikett">Analys</span></template>
          </td>
          <td class="tal" data-testid="antal-processer">
            <template v-if="d.processer">{{ d.processer }} <span class="analysetikett">Analys</span></template>
          </td>
        </tr>
      </tbody>
    </table>
    <p class="kallrad" data-testid="kallrad">
      Källa: <a :href="data.kalla.url" target="_blank" rel="noopener">harnosand.se, {{ data.kalla.titel }}</a> ·
      Kontrollerad {{ datum(data.kalla.kontrollerad) }}
    </p>
  </section>
</template>

<style scoped>
.vyhuvud {
  margin-bottom: 16px;
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
.filter select,
.filter input {
  font: inherit;
  padding: 4px 8px;
  border: 1px solid var(--line-strong);
  border-radius: var(--radius);
  background: var(--surface-raised);
  color: var(--ink);
  max-width: 260px;
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
  max-width: 48ch;
}
.saknas {
  color: var(--ink-muted);
}
.analysetikett {
  font-size: 12px;
  font-weight: 600;
  color: var(--ink-secondary);
  border: 1px dashed var(--line-strong);
  border-radius: var(--radius);
  padding: 0 6px;
}
.kallrad {
  margin: 12px 0 0;
  font-size: 12px;
  color: var(--ink-muted);
}
.fel {
  color: var(--status-critical);
}
</style>
