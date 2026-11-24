<script setup lang="ts">
// Liggande divergerande staplar, en per rad, för en avvikelse mot budget med ett streck för prognosen. Samma
// uppbyggnad som Brodiagram så att långa namn får plats i mobilbredd. Färgerna följer den divergerande skalan i
// docs/design.md: plus är blått och minus rött ("lägre", inte "dåligt"). Tecknet bär informationen.
import { computed, ref } from 'vue'
import { skillnad } from '../analys'

export interface Avvikelserad {
  id: string
  titel: string
  /** Avvikelsen som stapeln visar. */
  varde: number
  procent: number | null
  /** Prognosens avvikelse, ritas som ett streck. */
  prognos: number | null
  /** Rader i tooltipen, t.ex. avvikelsen mot den antagna budgeten. */
  detaljer: string[]
  kalla: string[]
}

const props = defineProps<{ rader: Avvikelserad[]; enhet: string; etikett: string; prognosetikett: string }>()

const doman = computed(() => {
  const alla = props.rader.flatMap((r) => [r.varde, r.prognos ?? 0])
  const min = Math.min(0, ...alla)
  const max = Math.max(0, ...alla)
  return { min, spann: max - min || 1 }
})
const pos = (x: number) => ((x - doman.value.min) / doman.value.spann) * 100
const procent = (p: number | null) => (p === null ? '' : ` (${skillnad(p, '').trim()} %)`)

const aktiv = ref<string | null>(null)
</script>

<template>
  <div class="avvikelse">
    <div class="rader" role="list" :aria-label="`${etikett}, ${enhet}`" @mouseleave="aktiv = null">
      <div
        v-for="r in rader"
        :key="r.id"
        class="rad"
        :class="{ aktiv: aktiv === r.id }"
        role="listitem"
        data-testid="avvikelsestapel"
        :data-organ="r.id"
        @mouseenter="aktiv = r.id"
      >
        <span class="titel">{{ r.titel }}</span>
        <span class="spar" aria-hidden="true">
          <span class="noll" :style="{ left: `${pos(0)}%` }" />
          <span
            class="stapel"
            :class="r.varde < 0 ? 'lagre' : 'hogre'"
            :style="{ left: `${pos(Math.min(r.varde, 0))}%`, width: `${Math.max(Math.abs(pos(r.varde) - pos(0)), 0.4)}%` }"
          />
          <span
            v-if="r.prognos !== null"
            class="prognos"
            :style="{ left: `${pos(r.prognos)}%` }"
            data-testid="prognosstreck"
          />
        </span>
        <span class="varde tal" data-testid="avvikelsevarde">{{ skillnad(r.varde, enhet) }}</span>
        <span v-if="aktiv === r.id" class="tips" role="tooltip">
          <strong>{{ r.titel }}</strong>
          <span class="tal">{{ skillnad(r.varde, enhet) }}{{ procent(r.procent) }} mot reviderad budget</span>
          <span v-for="d in r.detaljer" :key="d" class="tal tipsdetalj">{{ d }}</span>
          <span v-for="k in r.kalla" :key="k" class="tipskalla">{{ k }}</span>
        </span>
      </div>
    </div>
    <p class="forklaring">
      <span class="post"><span class="prov stapelprov hogre" aria-hidden="true" /> lägre nettokostnad än budgeten</span>
      <span class="post"><span class="prov stapelprov lagre" aria-hidden="true" /> högre nettokostnad än budgeten</span>
      <span class="post"><span class="prov prognosprov" aria-hidden="true" /> {{ prognosetikett }}</span>
    </p>
  </div>
</template>

<style scoped>
.avvikelse {
  font-size: 13px;
  margin-bottom: 16px;
}
.rader {
  display: flex;
  flex-direction: column;
  gap: 2px;
}
.rad {
  position: relative;
  display: grid;
  grid-template-columns: minmax(0, 13rem) minmax(80px, 1fr) 6rem;
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
.stapel.hogre {
  background: var(--diverg-hogre);
}
.stapel.lagre {
  background: var(--diverg-lagre);
}
.prognos {
  position: absolute;
  top: -1px;
  bottom: -1px;
  width: 0;
  margin-left: -1px;
  border-left: 2px solid var(--ink);
  z-index: 2;
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
}
.stapelprov {
  width: 12px;
  height: 10px;
  border-radius: 2px;
}
.stapelprov.hogre {
  background: var(--diverg-hogre);
}
.stapelprov.lagre {
  background: var(--diverg-lagre);
}
.prognosprov {
  width: 0;
  height: 14px;
  border-left: 2px solid var(--ink);
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
.tipsdetalj {
  color: var(--ink-secondary);
}
.tipskalla {
  font-size: 12px;
  color: var(--ink-muted);
}
</style>
