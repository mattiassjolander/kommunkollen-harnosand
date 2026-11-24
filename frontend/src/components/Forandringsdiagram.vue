<script setup lang="ts">
// Ett budgetförslags förändring av ramarna mot planförutsättningarna, en liggande divergerande stapel per nämnd
// (#147). Ett streck visar den antagna budgetens förändring för samma nämnd. Samma uppbyggnad som Avvikelsediagram,
// så att långa namn får plats i mobilbredd. Färgerna följer den divergerande skalan i docs/design.md: en högre ram
// är blå och en lägre röd ("lägre", inte "dåligt"). Tecknet bär informationen. En nämnd som förslaget inte anger
// står som en grå rad med texten "Anges inte", aldrig som noll.
import { computed, ref } from 'vue'
import { tal, talforandring } from '../format'

export interface Forandringsrad {
  organ: string
  /** Förändringen mot planförutsättningarna i mnkr. null = förslaget anger inte nämnden. */
  forandring: number | null
  /** Förslagets ram och planförutsättningarnas, för tooltipen. */
  ram: number | null
  plan: number | null
  /** Den antagna budgetens förändring för nämnden, ritas som ett streck. */
  antagen: number | null
  /** Text i stället för "Anges inte" när förslaget anger nämnden men förändringen saknas. */
  saknas?: string
  kalla: string
}

const props = defineProps<{ rader: Forandringsrad[]; streck: boolean; period: string }>()

const doman = computed(() => {
  const alla = props.rader.flatMap((r) => [r.forandring ?? 0, props.streck ? (r.antagen ?? 0) : 0])
  const min = Math.min(0, ...alla)
  const max = Math.max(0, ...alla)
  return { min, spann: max - min || 1 }
})
const pos = (x: number) => ((x - doman.value.min) / doman.value.spann) * 100

const aktiv = ref<string | null>(null)
</script>

<template>
  <div class="forandring">
    <div class="rader" role="list" :aria-label="`Förändring mot planförutsättningarna per nämnd ${period}, mnkr`" @mouseleave="aktiv = null">
      <div
        v-for="r in rader"
        :key="r.organ"
        class="rad"
        :class="{ aktiv: aktiv === r.organ, anges: r.forandring === null && !r.saknas }"
        role="listitem"
        data-testid="forandringsstapel"
        :data-organ="r.organ"
        @mouseenter="aktiv = r.organ"
      >
        <span class="titel">{{ r.organ }}</span>
        <span class="spar" aria-hidden="true">
          <template v-if="r.forandring !== null">
            <span class="noll" :style="{ left: `${pos(0)}%` }" />
            <span
              class="stapel"
              :class="r.forandring < 0 ? 'lagre' : 'hogre'"
              :style="{
                left: `${pos(Math.min(r.forandring, 0))}%`,
                width: `${Math.max(Math.abs(pos(r.forandring) - pos(0)), 0.4)}%`,
              }"
            />
          </template>
          <span
            v-if="streck && r.antagen !== null"
            class="antagenstreck"
            :style="{ left: `${pos(r.antagen)}%` }"
            data-testid="antagenstreck"
          />
        </span>
        <span v-if="r.forandring === null" class="varde saknas" :data-testid="r.saknas ? undefined : 'anges-inte'">{{ r.saknas ?? 'Anges inte' }}</span>
        <span v-else class="varde tal" data-testid="forandringsvarde">{{ talforandring(r.forandring, 'mnkr') }}</span>
        <span v-if="streck && r.antagen !== null" class="dold">, antagen budget {{ talforandring(r.antagen, 'mnkr') }}</span>
        <span v-if="aktiv === r.organ" class="tips" role="tooltip">
          <strong>{{ r.organ }} {{ period }}</strong>
          <template v-if="r.forandring !== null">
            <span class="tal">{{ talforandring(r.forandring, 'mnkr') }} mot planförutsättningarna</span>
            <span class="tal tipsdetalj">Ram {{ tal(r.ram, 'mnkr') }}, planförutsättningar {{ tal(r.plan, 'mnkr') }}</span>
          </template>
          <span v-else>{{ r.saknas ?? 'Förslaget anger inte nämnden' }}</span>
          <span v-if="streck && r.antagen !== null" class="tal tipsdetalj">Antagen budget {{ talforandring(r.antagen, 'mnkr') }}</span>
          <span class="tipskalla">{{ r.kalla }}</span>
        </span>
      </div>
    </div>
    <p class="forklaring">
      <span class="post"><span class="prov stapelprov hogre" aria-hidden="true" /> högre ram än planförutsättningarna</span>
      <span class="post"><span class="prov stapelprov lagre" aria-hidden="true" /> lägre ram än planförutsättningarna</span>
      <span v-if="streck" class="post"><span class="prov streckprov" aria-hidden="true" /> den antagna budgetens förändring</span>
    </p>
  </div>
</template>

<style scoped>
.forandring {
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
.rad.anges .titel {
  color: var(--ink-muted);
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
.antagenstreck {
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
.saknas {
  color: var(--ink-muted);
  font-style: italic;
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
.streckprov {
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
.dold {
  position: absolute;
  width: 1px;
  height: 1px;
  overflow: hidden;
  clip: rect(0 0 0 0);
}
</style>
