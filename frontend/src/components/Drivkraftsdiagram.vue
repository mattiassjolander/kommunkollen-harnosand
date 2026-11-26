<script setup lang="ts">
// Vad som drev en revidering av skatteunderlagsprognosen (#161): ändringen per rad i prognosunderlaget mellan två
// cirkulär för ett år, som liggande divergerande staplar. Samma uppbyggnad som Forandringsdiagram, så att långa
// namn får plats i mobilbredd. En höjning är blå och en sänkning röd ("lägre", inte "dåligt"). Tecknet bär
// informationen. Rader utan ändring visas inte.
import { computed, ref } from 'vue'
import { talforandring } from '../format'
import type { Drivkraft } from '../revideringar'

const props = defineProps<{ rader: Drivkraft[]; rubrik: string; kalla: string }>()

const mnkr = (tkr: number) => talforandring(Math.round(tkr / 100) / 10 || 0, 'mnkr')
const doman = computed(() => {
  const alla = props.rader.map((r) => r.tkr)
  const min = Math.min(0, ...alla)
  const max = Math.max(0, ...alla)
  return { min, spann: max - min || 1 }
})
const pos = (x: number) => ((x - doman.value.min) / doman.value.spann) * 100

const aktiv = ref<string | null>(null)
</script>

<template>
  <div class="drivkrafter">
    <div class="rader" role="list" :aria-label="rubrik" @mouseleave="aktiv = null">
      <div
        v-for="r in rader"
        :key="r.id"
        class="rad"
        :class="{ aktiv: aktiv === r.id }"
        role="listitem"
        data-testid="drivkraft"
        :data-rad="r.id"
        @mouseenter="aktiv = r.id"
      >
        <span class="titel">{{ r.etikett }}</span>
        <span class="spar" aria-hidden="true">
          <span class="noll" :style="{ left: `${pos(0)}%` }" />
          <span
            class="stapel"
            :class="r.tkr < 0 ? 'lagre' : 'hogre'"
            :style="{ left: `${pos(Math.min(r.tkr, 0))}%`, width: `${Math.max(Math.abs(pos(r.tkr) - pos(0)), 0.4)}%` }"
          />
        </span>
        <span class="varde tal" data-testid="drivkraftsvarde">{{ mnkr(r.tkr) }}</span>
        <span v-if="aktiv === r.id" class="tips" role="tooltip">
          <strong>{{ r.etikett }}</strong>
          <span class="tal">{{ mnkr(r.tkr) }}</span>
          <span class="tipskalla">{{ kalla }}</span>
        </span>
      </div>
    </div>
    <p class="forklaring">
      <span class="post"><span class="prov hogre" aria-hidden="true" /> höjer prognosen</span>
      <span class="post"><span class="prov lagre" aria-hidden="true" /> sänker prognosen</span>
    </p>
  </div>
</template>

<style scoped>
.drivkrafter {
  font-size: 13px;
}
.rader {
  display: flex;
  flex-direction: column;
  gap: 2px;
}
.rad {
  position: relative;
  display: grid;
  grid-template-columns: minmax(0, 15rem) minmax(80px, 1fr) 6rem;
  align-items: center;
  gap: 4px 12px;
  padding: 3px 0;
}
.rad.aktiv {
  background: var(--accent-wash);
}
@media (max-width: 560px) {
  .rad {
    grid-template-columns: minmax(0, 1fr) auto;
  }
  .spar {
    grid-column: 1 / -1;
    grid-row: 2;
  }
}
.titel {
  color: var(--ink);
}
.spar {
  position: relative;
  height: 18px;
}
.noll {
  position: absolute;
  top: -5px;
  bottom: -5px;
  border-left: 1px solid var(--ink-secondary);
  z-index: 1;
}
.stapel {
  position: absolute;
  top: 3px;
  bottom: 3px;
  border-radius: 2px;
}
.stapel.hogre,
.prov.hogre {
  background: var(--diverg-hogre);
}
.stapel.lagre,
.prov.lagre {
  background: var(--diverg-lagre);
}
.varde {
  text-align: right;
  white-space: nowrap;
  font-variant-numeric: tabular-nums;
}
.forklaring {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 4px 16px;
  margin: 8px 0 0;
  font-size: 12px;
  color: var(--ink-muted);
}
.post {
  display: inline-flex;
  align-items: center;
  gap: 6px;
}
.prov {
  display: inline-block;
  width: 12px;
  height: 10px;
  border-radius: 2px;
}
.tips {
  position: absolute;
  right: 0;
  bottom: 100%;
  z-index: 3;
  background: var(--surface-raised);
  border: 1px solid var(--line);
  border-radius: var(--radius);
  box-shadow: var(--shadow-float);
  padding: 8px 12px;
  display: flex;
  flex-direction: column;
  pointer-events: none;
  white-space: nowrap;
}
.tipskalla {
  font-size: 12px;
  color: var(--ink-muted);
}
</style>
