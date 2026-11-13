<script setup lang="ts">
// Stapeldiagram för en tidsserie med en serie. Följer dataviz-reglerna i docs/design.md:
// nollbaslinje, 4 px rundning på dataänden, hårlinjerutnät och tooltip vid hover.
import { computed, ref } from 'vue'
import { axeltal, tal } from '../format'

const props = defineProps<{
  punkter: { period: string; varde: number | null }[]
  enhet: string
  kalla: string
}>()

const B = 720
const H = 280
const M = { top: 16, right: 16, bottom: 32, left: 72 }
const inreB = B - M.left - M.right
const inreH = H - M.top - M.bottom

function snyggtSteg(spann: number): number {
  const rå = spann / 4
  const pot = 10 ** Math.floor(Math.log10(rå || 1))
  const f = rå / pot
  return (f <= 1 ? 1 : f <= 2 ? 2 : f <= 5 ? 5 : 10) * pot
}

const skala = computed(() => {
  const v = props.punkter.map((p) => p.varde ?? 0)
  const steg = snyggtSteg(Math.max(...v, 0) - Math.min(...v, 0))
  const min = Math.floor(Math.min(...v, 0) / steg) * steg
  const max = Math.ceil(Math.max(...v, 0) / steg) * steg || steg
  const y = (x: number) => M.top + ((max - x) / (max - min)) * inreH
  const ticks: number[] = []
  for (let t = min; t <= max + steg / 2; t += steg) ticks.push(t)
  return { y, ticks, steg }
})

// Med många år visas bara var n:te årsetikett så att de inte krockar.
const etikettVarje = computed(() => Math.ceil(props.punkter.length / 12))
function visaEtikett(i: number): boolean {
  const n = props.punkter.length
  return (n - 1 - i) % etikettVarje.value === 0
}

const band = computed(() => inreB / Math.max(props.punkter.length, 1))
const stapelB = computed(() => Math.min(48, band.value * 0.6))

function stapel(i: number, varde: number): string {
  const { y } = skala.value
  const x = M.left + band.value * i + (band.value - stapelB.value) / 2
  const y0 = y(0)
  const y1 = y(varde)
  const w = stapelB.value
  const h = Math.abs(y1 - y0)
  const r = Math.min(4, h, w / 2)
  if (varde >= 0) {
    return `M${x},${y0} V${y1 + r} Q${x},${y1} ${x + r},${y1} H${x + w - r} Q${x + w},${y1} ${x + w},${y1 + r} V${y0} Z`
  }
  return `M${x},${y0} V${y1 - r} Q${x},${y1} ${x + r},${y1} H${x + w - r} Q${x + w},${y1} ${x + w},${y1 - r} V${y0} Z`
}

const aktiv = ref<number | null>(null)
const tipsX = computed(() =>
  aktiv.value === null ? 0 : ((M.left + band.value * (aktiv.value + 0.5)) / B) * 100,
)
</script>

<template>
  <div class="diagram">
    <svg :viewBox="`0 0 ${B} ${H}`" role="img" :aria-label="`Stapeldiagram, ${enhet}`" @mouseleave="aktiv = null">
      <g class="rutnat">
        <g v-for="t in skala.ticks" :key="t">
          <line :x1="M.left" :x2="B - M.right" :y1="skala.y(t)" :y2="skala.y(t)" :class="{ bas: t === 0 }" />
          <text :x="M.left - 8" :y="skala.y(t)" text-anchor="end" dominant-baseline="middle" class="tal">
            {{ axeltal(t, skala.steg) }}
          </text>
        </g>
      </g>
      <g v-for="(p, i) in punkter" :key="p.period">
        <rect
          :x="M.left + band * i"
          :y="M.top"
          :width="band"
          :height="inreH"
          class="traffyta"
          :class="{ aktiv: aktiv === i }"
          @mouseenter="aktiv = i"
        />
        <path v-if="p.varde !== null" :d="stapel(i, p.varde)" class="stapel" data-testid="stapel" />
        <template v-if="p.varde === null">
          <!-- Saknat värde ritas aldrig som noll: ordet där det får plats, annars ett streck med förklaring. -->
          <text
            v-if="band >= 48"
            :x="M.left + band * (i + 0.5)"
            :y="skala.y(0) - 6"
            text-anchor="middle"
            class="saknas"
            data-testid="saknas"
          >
            saknas
          </text>
          <line
            v-else
            :x1="M.left + band * (i + 0.5) - 3"
            :x2="M.left + band * (i + 0.5) + 3"
            :y1="skala.y(0) - 6"
            :y2="skala.y(0) - 6"
            class="saknasstreck"
            data-testid="saknas"
          />
        </template>
        <text v-if="visaEtikett(i)" :x="M.left + band * (i + 0.5)" :y="H - 10" text-anchor="middle" class="tal">
          {{ p.period }}
        </text>
      </g>
    </svg>
    <p v-if="band < 48 && punkter.some((p) => p.varde === null)" class="forklaring">
      <svg width="12" height="8" aria-hidden="true"><line x1="3" x2="9" y1="4" y2="4" class="saknasstreck" /></svg>
      Uppgift saknas
    </p>
    <div v-if="aktiv !== null" class="tips" :style="{ left: `${tipsX}%` }" role="tooltip">
      <strong>{{ punkter[aktiv].period }}</strong>
      <span class="tal">{{ tal(punkter[aktiv].varde, enhet) }}</span>
      <span class="tipskalla">{{ kalla }}</span>
    </div>
  </div>
</template>

<style scoped>
.diagram {
  position: relative;
}
.diagram > svg {
  width: 100%;
  height: auto;
  display: block;
}
.rutnat line {
  stroke: var(--line);
  stroke-width: 1;
}
.rutnat line.bas {
  stroke: var(--line-strong);
}
text {
  fill: var(--ink-muted);
  font-size: 12px;
}
.saknas {
  font-size: 11px;
  font-style: italic;
}
.saknasstreck {
  stroke: var(--ink-secondary);
  stroke-width: 2;
}
.forklaring {
  display: flex;
  align-items: center;
  gap: 4px;
  margin: 4px 0 0;
  font-size: 12px;
  color: var(--ink-muted);
}
.stapel {
  fill: var(--series-1);
  pointer-events: none;
}
.traffyta {
  fill: transparent;
}
.traffyta.aktiv {
  fill: var(--accent-wash);
  opacity: 0.5;
}
.tips {
  position: absolute;
  top: 0;
  transform: translateX(-50%);
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
