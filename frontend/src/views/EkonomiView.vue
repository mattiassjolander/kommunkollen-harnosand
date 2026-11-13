<script setup lang="ts">
import { computed, inject, onMounted, ref } from 'vue'
import { EjInloggad, hamtaSerie, type Serie } from '../api'
import { tal } from '../format'
import Kallrad from '../components/Kallrad.vue'
import Stapeldiagram from '../components/Stapeldiagram.vue'

const MATT = 'kolada:N03007'
const FORSTA_AR = 2022 // standardvisning enligt kravspec avsnitt 18

const serie = ref<Serie | null>(null)
const laddar = ref(true)
const fel = ref<string | null>(null)
const utloggad = inject<() => void>('utloggad', () => {})

onMounted(async () => {
  try {
    serie.value = await hamtaSerie(MATT)
  } catch (e) {
    if (e instanceof EjInloggad) return utloggad()
    fel.value = e instanceof Error ? e.message : String(e)
  } finally {
    laddar.value = false
  }
})

const punkter = computed(() => (serie.value?.punkter ?? []).filter((p) => Number(p.period) >= FORSTA_AR))
const kallnamn = computed(() => (serie.value ? `Källa: ${serie.value.matt.datakalla.titel}` : ''))
</script>

<template>
  <header class="vyhuvud">
    <h1>Ekonomi</h1>
    <p class="ingress">Härnösands kommuns ekonomiska utveckling över tid.</p>
  </header>

  <p v-if="laddar">Hämtar uppgifter…</p>
  <p v-else-if="fel" class="fel">Kunde inte hämta uppgifter: {{ fel }}</p>
  <p v-else-if="!serie" data-testid="tomt">Uppgift saknas. Ingen insamling har körts än.</p>

  <section v-else class="kort" data-testid="nyckeltal">
    <h3>{{ serie.matt.titel }}</h3>
    <p class="beskrivning">{{ serie.matt.beskrivning }}</p>
    <Stapeldiagram :punkter="punkter" :enhet="serie.matt.enhet" :kalla="kallnamn" />
    <table class="tabell">
      <caption class="dold">{{ serie.matt.titel }}</caption>
      <thead>
        <tr>
          <th scope="col">År</th>
          <th scope="col" class="hoger">{{ serie.matt.enhet }}</th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="p in punkter" :key="p.period">
          <td class="tal">{{ p.period }}</td>
          <td class="tal hoger">{{ tal(p.varde) }}</td>
        </tr>
      </tbody>
    </table>
    <Kallrad :serie="serie" :perioder="punkter.map((p) => p.period)" />
  </section>
</template>

<style scoped>
.vyhuvud {
  margin-bottom: 24px;
}
.ingress {
  color: var(--ink-secondary);
  margin: 0;
}
.kort {
  background: var(--surface);
  border: 1px solid var(--line);
  border-radius: var(--radius);
  padding: 24px;
  max-width: 880px;
}
.beskrivning {
  color: var(--ink-secondary);
  margin: 4px 0 16px;
  max-width: 70ch;
}
.tabell {
  border-collapse: collapse;
  margin-top: 16px;
  font-size: 13px;
  min-width: 240px;
}
.tabell th,
.tabell td {
  padding: 4px 12px 4px 0;
  border-bottom: 1px solid var(--line);
  text-align: left;
}
.tabell th {
  color: var(--ink-secondary);
  font-weight: 600;
}
.hoger {
  text-align: right !important;
}
.dold {
  position: absolute;
  width: 1px;
  height: 1px;
  overflow: hidden;
  clip: rect(0 0 0 0);
}
.fel {
  color: var(--status-critical);
}
</style>
