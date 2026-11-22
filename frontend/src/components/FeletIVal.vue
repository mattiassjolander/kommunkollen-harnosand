<script setup lang="ts">
// Var felet som en rättelse rättar finns (#74): i protokollet (källan saknar eller anger fel uppgift) eller i
// inläsningen (plattformen läste eller tolkade fel). Valet är obligatoriskt. Fel i protokollet märker protokollet
// "Innehåller felaktigheter" när rättelsen publiceras.
import type { FeletI } from '../api'

const modell = defineModel<FeletI | null>({ required: true })
const namn = `felet-i-${Math.random().toString(36).slice(2)}`
</script>

<template>
  <fieldset class="val" data-testid="felet-i">
    <legend>Var finns felet?</legend>
    <label>
      <input v-model="modell" type="radio" :name="namn" value="protokollet" required data-testid="felet-i-protokollet" />
      I protokollet
      <span class="hjalp">Protokollet saknar eller anger fel uppgift.</span>
    </label>
    <label>
      <input v-model="modell" type="radio" :name="namn" value="inlasningen" data-testid="felet-i-inlasningen" />
      I inläsningen
      <span class="hjalp">Plattformen läste eller tolkade protokollet fel.</span>
    </label>
  </fieldset>
</template>

<style scoped>
.val {
  border: 0;
  padding: 0;
  margin: 0;
  display: grid;
  gap: 4px;
  font-size: 13px;
  color: var(--ink-secondary);
}
legend {
  padding: 0;
  margin-bottom: 4px;
}
label {
  display: flex;
  gap: 6px;
  align-items: baseline;
  flex-wrap: wrap;
  color: var(--ink);
}
.hjalp {
  font-size: 12px;
  color: var(--ink-muted);
}
</style>
