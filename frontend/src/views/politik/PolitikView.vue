<script setup lang="ts">
import { computed, inject, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { EjInloggad, hamtaOrgan, hamtaSammantraden, type Organ, type Sammantradesrad } from '../../api'
import { sammantradesdatum } from '../../format'
import Tolkningsmarkering from '../../components/Tolkningsmarkering.vue'

const route = useRoute()
const router = useRouter()
const utloggad = inject<() => void>('utloggad', () => {})

const organ = ref<Organ[]>([])
const sammantraden = ref<Sammantradesrad[]>([])
const laddar = ref(true)
const fel = ref<string | null>(null)

const valtOrgan = computed<string>({
  get: () => (typeof route.query.organ === 'string' ? route.query.organ : ''),
  set: (v) => router.replace({ query: { ...route.query, organ: v || undefined } }),
})

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
onMounted(ladda)
watch(valtOrgan, ladda)

// Sammanträdena grupperade per år, senaste först (API:t sorterar redan).
const perAr = computed(() => {
  const grupper = new Map<string, Sammantradesrad[]>()
  for (const s of sammantraden.value) {
    const ar = s.datum?.slice(0, 4) ?? 'Datum okänt'
    grupper.set(ar, [...(grupper.get(ar) ?? []), s])
  }
  return [...grupper.entries()]
})

const tid = (s: Sammantradesrad) => (s.starttid ? `${s.starttid}${s.sluttid ? `–${s.sluttid}` : ''}` : '–')
const paragrafer = (s: Sammantradesrad) =>
  !s.paragrafer ? '–' : s.paragrafer[0] === s.paragrafer[1] ? `§ ${s.paragrafer[0]}` : `§§ ${s.paragrafer[0]}–${s.paragrafer[1]}`
</script>

<template>
  <header class="vyhuvud">
    <h1>Politik och beslut</h1>
    <p class="ingress">
      Sammanträden i kommunens beslutande organ, med närvaro och de ärenden som behandlades. Uppgifterna är automatiskt
      lästa ur de justerade protokollen på harnosand.se och inte granskade av redaktionen. Varje uppgift länkar till
      protokollet.
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
  </div>

  <p v-if="laddar">Hämtar uppgifter…</p>
  <p v-else-if="fel" class="fel">Kunde inte hämta uppgifter: {{ fel }}</p>
  <p v-else-if="!sammantraden.length" class="ingress">Inga protokoll har hämtats än.</p>

  <section v-for="[ar, rader] in perAr" v-else :key="ar" class="kort" :aria-labelledby="`ar-${ar}`">
    <h2 :id="`ar-${ar}`">{{ ar }}</h2>
    <table class="tabell" data-testid="sammantraden">
      <thead>
        <tr>
          <th scope="col">Sammanträde</th>
          <th scope="col">Organ</th>
          <th scope="col">Tid</th>
          <th scope="col">Paragrafer</th>
          <th scope="col" class="hoger">Behandlingar</th>
          <th scope="col">Underlag</th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="s in rader" :key="s.id" data-testid="sammantrade" :data-datum="s.datum">
          <th scope="row">
            <RouterLink :to="`/politik/sammantraden/${s.id}`">{{ sammantradesdatum(s.datum) }}</RouterLink>
          </th>
          <td>{{ s.organ.namn }}</td>
          <td class="tal">{{ tid(s) }}</td>
          <td class="tal">{{ paragrafer(s) }}</td>
          <td class="tal hoger">{{ s.antal_behandlingar }}</td>
          <td><Tolkningsmarkering :ej-tolkad="s.tolkning === 'ej_tolkad'" /></td>
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
</style>
