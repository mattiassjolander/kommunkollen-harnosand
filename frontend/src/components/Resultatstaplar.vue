<script setup lang="ts">
// Stående staplar för några belopp i följd, t.ex. årets resultat från antagen budget till utfall. Byggt i HTML
// i stället för SVG så att kategorinamnen radbryts och texten behåller sin storlek i mobilbredd. Följer
// dataviz-reglerna i docs/design.md: nollbaslinje, 4 px rundning på dataänden, värdet direkt vid stapeln och
// tooltip vid hover. Jämförelsestaplarna är grå och den markerade (utfallet) har seriefärgen.
import { computed, ref } from 'vue'
import { tal } from '../format'
import { skillnad } from '../analys'

export interface Resultatstapel {
  id: string
  titel: string
  varde: number
  /** Källan med sida, t.ex. "Årsredovisning 2025, s. 48". */
  kalla: string
  /** Ritas i seriefärgen, övriga grå. */
  markerad?: boolean
}

const props = defineProps<{
  staplar: Resultatstapel[]
  enhet: string
  /** Streckad referenslinje tvärs över diagrammet, t.ex. den antagna budgeten. */
  referens?: { titel: string; varde: number } | null
  etikett: string
}>()

// Plats ovanför och under staplarna för värdetexten.
const doman = computed(() => {
  const v = [...props.staplar.map((s) => s.varde), props.referens?.varde ?? 0, 0]
  const max = Math.max(...v)
  const min = Math.min(...v)
  const spann = max - min || 1
  const topp = max + (max > 0 ? spann * 0.18 : 0)
  const botten = min - (min < 0 ? spann * 0.18 : 0)
  return { botten, spann: topp - botten || 1 }
})
const pos = (x: number) => ((x - doman.value.botten) / doman.value.spann) * 100

const aktiv = ref<string | null>(null)
</script>

<template>
  <div class="resultatstaplar" @mouseleave="aktiv = null">
    <div class="yta" role="list" :aria-label="`${etikett}, ${enhet}`">
      <span class="noll" :style="{ bottom: `${pos(0)}%` }" aria-hidden="true" />
      <span
        v-if="referens"
        class="referens"
        :style="{ bottom: `${pos(referens.varde)}%` }"
        aria-hidden="true"
        data-testid="referenslinje"
      />
      <div
        v-for="s in staplar"
        :key="s.id"
        class="kolumn"
        :class="{ aktiv: aktiv === s.id }"
        role="listitem"
        :aria-label="`${s.titel}: ${tal(s.varde, enhet)}`"
        data-testid="resultatstapel"
        :data-stapel="s.id"
        @mouseenter="aktiv = s.id"
      >
        <span
          class="stapel"
          :class="[s.markerad ? 'markerad' : 'neutral', s.varde < 0 ? 'negativ' : 'positiv']"
          :style="{ bottom: `${pos(Math.min(s.varde, 0))}%`, height: `${Math.max(Math.abs(pos(s.varde) - pos(0)), 0.5)}%` }"
          aria-hidden="true"
        />
        <span
          class="varde tal"
          :class="{ under: s.varde < 0 }"
          :style="s.varde < 0 ? { top: `${100 - pos(s.varde)}%` } : { bottom: `${pos(s.varde)}%` }"
          data-testid="resultatvarde"
        >{{ tal(s.varde, enhet) }}</span>
        <span v-if="aktiv === s.id" class="tips" role="tooltip">
          <strong>{{ s.titel }}</strong>
          <span class="tal">{{ tal(s.varde, enhet) }}</span>
          <span v-if="referens && s.id !== 'antagen'" class="tal tipsjamforelse">
            {{ skillnad(s.varde - referens.varde, enhet) }} mot {{ referens.titel.toLowerCase() }}
          </span>
          <span class="tipskalla">{{ s.kalla }}</span>
        </span>
      </div>
    </div>
    <div class="titlar" aria-hidden="true">
      <span v-for="s in staplar" :key="s.id" :class="{ markerad: s.markerad }">{{ s.titel }}</span>
    </div>
    <p v-if="referens" class="forklaring" data-testid="referensforklaring">
      <svg width="18" height="8" aria-hidden="true"><line x1="0" x2="18" y1="4" y2="4" class="referensprov" /></svg>
      {{ referens.titel }} ({{ tal(referens.varde, enhet) }})
    </p>
  </div>
</template>

<style scoped>
.resultatstaplar {
  font-size: 13px;
  margin-bottom: 16px;
}
.yta,
.titlar {
  display: grid;
  grid-auto-columns: minmax(0, 1fr);
  grid-auto-flow: column;
  gap: 2px;
}
.yta {
  position: relative;
  height: 180px;
  border-bottom: 1px solid transparent;
}
.noll {
  position: absolute;
  left: 0;
  right: 0;
  border-top: 1px solid var(--line-strong);
  pointer-events: none;
}
.referens {
  position: absolute;
  left: 0;
  right: 0;
  z-index: 1;
  border-top: 2px dashed var(--ink);
  pointer-events: none;
}
.referensprov {
  stroke: var(--ink);
  stroke-width: 2;
  stroke-dasharray: 5 3;
}
.kolumn {
  position: relative;
}
.kolumn.aktiv {
  background: var(--accent-wash);
}
.stapel {
  position: absolute;
  left: 50%;
  width: min(56px, 60%);
  transform: translateX(-50%);
}
.stapel.positiv {
  border-radius: var(--radius-mark) var(--radius-mark) 0 0;
}
.stapel.negativ {
  border-radius: 0 0 var(--radius-mark) var(--radius-mark);
}
.stapel.neutral {
  background: var(--ink-muted);
}
.stapel.markerad {
  background: var(--series-1);
}
.varde {
  position: absolute;
  left: 0;
  right: 0;
  margin-bottom: 4px;
  text-align: center;
  white-space: nowrap;
  color: var(--ink);
  font-variant-numeric: tabular-nums;
}
.varde.under {
  margin: 4px 0 0;
}
.titlar {
  margin-top: 6px;
}
.titlar span {
  text-align: center;
  font-size: 12px;
  color: var(--ink-secondary);
  overflow-wrap: anywhere;
  hyphens: auto;
}
.titlar span.markerad {
  color: var(--ink);
  font-weight: 600;
}
.forklaring {
  display: flex;
  align-items: center;
  gap: 6px;
  margin: 8px 0 0;
  font-size: 12px;
  color: var(--ink-muted);
}
.tips {
  position: absolute;
  bottom: 100%;
  left: 50%;
  transform: translateX(-50%);
  z-index: 2;
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
.kolumn:first-child .tips {
  left: 0;
  transform: none;
}
.kolumn:last-child .tips {
  left: auto;
  right: 0;
  transform: none;
}
.tipsjamforelse {
  color: var(--ink-secondary);
}
.tipskalla {
  font-size: 12px;
  color: var(--ink-muted);
}
</style>
