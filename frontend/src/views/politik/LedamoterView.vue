<script setup lang="ts">
import { computed, inject, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { EjInloggad, hamtaLedamoter, hamtaOrgan, type Ledamotsrad, type Organ } from '../../api'
import { parti as partitext } from '../../format'
import Partimarkering from '../../components/Partimarkering.vue'

const route = useRoute()
const router = useRouter()
const utloggad = inject<() => void>('utloggad', () => {})

const ledamoter = ref<Ledamotsrad[]>([])
const organ = ref<Organ[]>([])
const laddar = ref(true)
const fel = ref<string | null>(null)

// Sökning och filter speglas i URL:en, så att en vy går att dela.
function fraga(namn: string) {
  return computed<string>({
    get: () => (typeof route.query[namn] === 'string' ? (route.query[namn] as string) : ''),
    set: (v) => router.replace({ query: { ...route.query, [namn]: v || undefined } }),
  })
}
const sok = fraga('q')
const valtParti = fraga('parti')
const valtOrgan = fraga('organ')

onMounted(async () => {
  try {
    ;[ledamoter.value, organ.value] = await Promise.all([hamtaLedamoter(), hamtaOrgan()])
  } catch (e) {
    if (e instanceof EjInloggad) return utloggad()
    fel.value = e instanceof Error ? e.message : String(e)
  } finally {
    laddar.value = false
  }
})

// Partierna i registret, alfabetiskt efter förkortning (design.md), partilös sist.
const partier = computed(() => {
  const alla = [...new Set(ledamoter.value.flatMap((l) => l.partier))]
  return alla.sort((a, b) => (a === '-' ? 1 : b === '-' ? -1 : a.localeCompare(b, 'sv')))
})

const urval = computed(() => {
  const q = sok.value.trim().toLocaleLowerCase('sv')
  return ledamoter.value.filter(
    (l) =>
      (!q || [l.namn, ...l.andra_namn].some((n) => n.toLocaleLowerCase('sv').includes(q))) &&
      (!valtParti.value || l.partier.includes(valtParti.value)) &&
      (!valtOrgan.value || l.organ.some((o) => o.id === valtOrgan.value)),
  )
})
</script>

<template>
  <header class="vyhuvud">
    <h1>Ledamöter</h1>
    <p class="ingress">
      Ledamöter och ersättare som förekommer i protokollens närvarolistor. Partiet är det som protokollet anger vid
      varje sammanträde, så ett partibyte syns. Uppgifterna är automatiskt lästa ur protokollen.
    </p>
  </header>

  <div class="filter">
    <label>
      Sök namn
      <input v-model="sok" type="search" placeholder="Namn" data-testid="sok-ledamot" />
    </label>
    <label>
      Parti
      <select v-model="valtParti" data-testid="parti-filter">
        <option value="">Alla partier</option>
        <option v-for="p in partier" :key="p" :value="p">{{ partitext(p) }}</option>
      </select>
    </label>
    <label>
      Organ
      <select v-model="valtOrgan" data-testid="organ">
        <option value="">Alla organ</option>
        <option v-for="o in organ" :key="o.id" :value="o.id">{{ o.namn }}</option>
      </select>
    </label>
  </div>

  <p v-if="laddar">Hämtar uppgifter…</p>
  <p v-else-if="fel" class="fel">Kunde inte hämta uppgifter: {{ fel }}</p>
  <p v-else-if="!ledamoter.length" class="ingress">Inga protokoll har hämtats än.</p>
  <section v-else class="kort" aria-labelledby="led-rubrik">
    <h2 id="led-rubrik">
      {{ urval.length === 1 ? '1 person' : `${urval.length} personer` }}
    </h2>
    <p v-if="!urval.length" class="ingress">Ingen matchar urvalet.</p>
    <table v-else class="tabell" data-testid="ledamoter">
      <thead>
        <tr>
          <th scope="col">Namn</th>
          <th scope="col">Parti senast</th>
          <th scope="col">Organ</th>
          <th scope="col" class="hoger">Sammanträden</th>
          <th scope="col">Senast</th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="l in urval" :key="l.id" data-testid="ledamot" :data-id="l.id">
          <th scope="row">
            <RouterLink :to="`/politik/ledamoter/${l.id}`">{{ l.namn }}</RouterLink>
            <span v-if="l.andra_namn.length" class="andra">även {{ l.andra_namn.join(', ') }}</span>
          </th>
          <td>
            <Partimarkering :parti="l.parti" />
            <span v-if="l.partier.length > 1" class="andra" data-testid="flera-partier">
              tidigare även {{ l.partier.filter((p) => p !== l.parti).map(partitext).join(', ') }}
            </span>
          </td>
          <td>{{ l.organ.map((o) => o.namn).join(', ') }}</td>
          <td class="tal hoger">{{ l.antal_sammantraden }}</td>
          <td class="tal">{{ l.senast ?? '–' }}</td>
        </tr>
      </tbody>
    </table>
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
.andra {
  display: block;
  font-size: 12px;
  font-weight: 400;
  color: var(--ink-muted);
}
.hoger {
  text-align: right !important;
}
.fel {
  color: var(--status-critical);
}
</style>
