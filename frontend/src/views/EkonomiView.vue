<script setup lang="ts">
import { computed, inject, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { EjInloggad, hamtaEkonomi, type Nyckeltalsgrupp } from '../api'
import Nyckeltalskort from '../components/Nyckeltalskort.vue'

const STANDARD_FRAN = 2022 // standardvisning enligt kravspec avsnitt 18

const route = useRoute()
const router = useRouter()
const grupper = ref<Nyckeltalsgrupp[]>([])
const laddar = ref(true)
const fel = ref<string | null>(null)
const utloggad = inject<() => void>('utloggad', () => {})

onMounted(async () => {
  try {
    grupper.value = (await hamtaEkonomi()).grupper
  } catch (e) {
    if (e instanceof EjInloggad) return utloggad()
    fel.value = e instanceof Error ? e.message : String(e)
  } finally {
    laddar.value = false
  }
})

// Alla år som någon serie har, så att man kan välja hur långt bakåt visningen ska börja.
const ar = computed(() => {
  const alla = new Set<number>()
  for (const g of grupper.value)
    for (const n of g.nyckeltal) for (const p of n.serie?.punkter ?? []) alla.add(Number(p.period))
  return [...alla].sort((a, b) => a - b)
})

// Filtret speglas i URL:en (?fran=2015) så att en vy går att länka till.
const franAr = ref(Number(route.query.fran) || STANDARD_FRAN)
watch(franAr, (v) => router.replace({ query: { ...route.query, fran: v === STANDARD_FRAN ? undefined : String(v) } }))

const harData = computed(() => grupper.value.some((g) => g.nyckeltal.some((n) => n.serie)))
</script>

<template>
  <header class="vyhuvud">
    <h1>Ekonomi</h1>
    <p class="ingress">
      Härnösands kommuns ekonomiska utveckling över tid. Belopp i löpande priser, alltså inte justerade för
      inflation. Kronor per invånare gör åren lättare att jämföra.
    </p>
  </header>

  <p v-if="laddar">Hämtar uppgifter…</p>
  <p v-else-if="fel" class="fel">Kunde inte hämta uppgifter: {{ fel }}</p>
  <p v-else-if="!harData" data-testid="tomt">Uppgift saknas. Ingen insamling har körts än.</p>

  <template v-else>
    <div class="filterrad">
      <label>
        Visa från
        <select v-model.number="franAr" data-testid="fran-ar">
          <option v-for="a in ar" :key="a" :value="a">{{ a }}</option>
        </select>
      </label>
      <nav class="hopp" aria-label="Avsnitt">
        <a v-for="g in grupper" :key="g.id" :href="`#${g.id}`">{{ g.titel }}</a>
      </nav>
    </div>

    <section v-for="g in grupper" :id="g.id" :key="g.id" class="grupp">
      <h2>{{ g.titel }}</h2>
      <div class="rutnat">
        <Nyckeltalskort v-for="n in g.nyckeltal" :key="n.id" :nyckeltal="n" :fran-ar="franAr" />
      </div>
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
.filterrad {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 12px 24px;
  margin-bottom: 32px;
  padding-bottom: 16px;
  border-bottom: 1px solid var(--line);
}
.filterrad label {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  color: var(--ink-secondary);
}
.filterrad select {
  font: inherit;
  padding: 4px 8px;
  border: 1px solid var(--line-strong);
  border-radius: var(--radius);
  background: var(--surface-raised);
  color: var(--ink);
}
.hopp {
  display: flex;
  flex-wrap: wrap;
  gap: 4px 16px;
  font-size: 13px;
}
.grupp {
  margin-bottom: 48px;
  scroll-margin-top: 16px;
}
.grupp h2 {
  margin-bottom: 16px;
}
.rutnat {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(min(100%, 520px), 1fr));
  gap: 16px;
}
.fel {
  color: var(--status-critical);
}
</style>
