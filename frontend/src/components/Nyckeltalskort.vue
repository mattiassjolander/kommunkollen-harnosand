<script setup lang="ts">
import { computed, ref } from 'vue'
import type { Nyckeltal } from '../api'
import { siffra, visningsskala } from '../format'
import Kallrad from './Kallrad.vue'
import Stapeldiagram from './Stapeldiagram.vue'

const props = defineProps<{ nyckeltal: Nyckeltal; franAr: number }>()
const visning = ref<'diagram' | 'tabell'>('diagram')

const serie = computed(() => props.nyckeltal.serie)
const skala = computed(() => visningsskala(serie.value?.matt.enhet ?? ''))
const punkter = computed(() =>
  (serie.value?.punkter ?? [])
    .filter((p) => Number(p.period) >= props.franAr)
    .map((p) => ({ period: p.period, varde: p.varde === null ? null : p.varde * skala.value.faktor })),
)
const kallnamn = computed(() => (serie.value ? `Källa: ${serie.value.matt.datakalla.titel}` : ''))
</script>

<template>
  <section class="kort" data-testid="nyckeltal" :data-matt="nyckeltal.id">
    <div class="huvud">
      <h3>{{ serie?.matt.titel ?? nyckeltal.id }}</h3>
      <div v-if="serie" class="vaxel" role="group" :aria-label="`Visa ${serie.matt.titel} som`">
        <button type="button" :aria-pressed="visning === 'diagram'" @click="visning = 'diagram'">Diagram</button>
        <button type="button" :aria-pressed="visning === 'tabell'" @click="visning = 'tabell'">Tabell</button>
      </div>
    </div>

    <p v-if="!serie" class="beskrivning">Uppgift saknas. Ingen insamling har hämtat det här nyckeltalet än.</p>
    <template v-else>
      <p class="beskrivning">{{ serie.matt.beskrivning }}</p>
      <p v-if="!punkter.length" class="beskrivning">Uppgift saknas för de valda åren.</p>
      <Stapeldiagram
        v-else-if="visning === 'diagram'"
        :punkter="punkter"
        :enhet="skala.enhet"
        :kalla="kallnamn"
      />
      <table v-else class="tabell">
        <caption class="dold">{{ serie.matt.titel }}</caption>
        <thead>
          <tr>
            <th scope="col">År</th>
            <th scope="col" class="hoger">{{ skala.enhet }}</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="p in punkter" :key="p.period">
            <td class="tal">{{ p.period }}</td>
            <td class="tal hoger" :class="{ saknas: p.varde === null }">{{ siffra(p.varde, skala.enhet) }}</td>
          </tr>
        </tbody>
      </table>
      <Kallrad :serie="serie" :perioder="punkter.map((p) => p.period)" :prisniva="nyckeltal.prisniva" />
    </template>
  </section>
</template>

<style scoped>
.kort {
  background: var(--surface);
  border: 1px solid var(--line);
  border-radius: var(--radius);
  padding: 24px;
  min-width: 0;
}
.huvud {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 12px;
}
.beskrivning {
  color: var(--ink-secondary);
  margin: 4px 0 16px;
  max-width: 70ch;
}
.vaxel {
  display: inline-flex;
  border: 1px solid var(--line-strong);
  border-radius: var(--radius);
  overflow: hidden;
  flex-shrink: 0;
}
.vaxel button {
  font: inherit;
  font-size: 12px;
  padding: 4px 10px;
  border: 0;
  background: var(--surface-raised);
  color: var(--ink-secondary);
  cursor: pointer;
}
.vaxel button + button {
  border-left: 1px solid var(--line-strong);
}
.vaxel button[aria-pressed='true'] {
  background: var(--accent-wash);
  color: var(--accent);
  font-weight: 600;
}
.tabell {
  border-collapse: collapse;
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
.saknas {
  color: var(--ink-muted);
  font-style: italic;
}
.dold {
  position: absolute;
  width: 1px;
  height: 1px;
  overflow: hidden;
  clip: rect(0 0 0 0);
}
</style>
