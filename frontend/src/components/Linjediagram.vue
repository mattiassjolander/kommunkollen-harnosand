<script setup lang="ts">
// Linjediagram med flera serier över år. Följer dataviz-reglerna i docs/design.md: 2 px linjer,
// hårlinjerutnät, teckenförklaring vid två eller fler serier och tooltip vid hover med värde, enhet,
// period och källa. Färgerna är den kategoriska paletten i fast ordning.
import { computed, ref } from 'vue'
import { axeltal, tal } from '../format'

const props = defineProps<{
  /** Ett saknat värde (null) bryter linjen. Det ritas aldrig som noll. */
  serier: { namn: string; punkter: { ar: number; varde: number | null }[] }[]
  enhet: string
  kalla: string
  /** Beskrivning för skärmläsare. */
  etikett: string
  /** Lägst värde överst, t.ex. för placeringar där plats 1 ska stå överst. */
  omvand?: boolean
  /** År då linjen bryts (t.ex. metodbyten): ingen linje dras från året före. Markeras med en streckad linje. */
  brott?: number[]
}>()

const B = 720
const H = 300
const M = { top: 16, right: 16, bottom: 32, left: 72 }
const inreB = B - M.left - M.right
const inreH = H - M.top - M.bottom

function snyggtSteg(spann: number): number {
  const rå = spann / 4
  const pot = 10 ** Math.floor(Math.log10(rå || 1))
  const f = rå / pot
  return (f <= 1 ? 1 : f <= 2 ? 2 : f <= 5 ? 5 : 10) * pot
}

const ar = computed(() => [...new Set(props.serier.flatMap((s) => s.punkter.map((p) => p.ar)))].sort((a, b) => a - b))
const skala = computed(() => {
  const v = props.serier.flatMap((s) => s.punkter.flatMap((p) => (p.varde === null ? [] : [p.varde])))
  const lag = Math.min(...v)
  const hog = Math.max(...v)
  const steg = snyggtSteg(hog - lag)
  const min = Math.floor(lag / steg) * steg
  const max = Math.ceil(hog / steg) * steg
  const y = (x: number) => M.top + ((props.omvand ? x - min : max - x) / (max - min || 1)) * inreH
  const ticks: number[] = []
  for (let t = min; t <= max + steg / 2; t += steg) ticks.push(t)
  return { y, ticks, steg }
})
const x = (a: number) => {
  const lista = ar.value
  return M.left + (lista.length > 1 ? ((a - lista[0]) / (lista[lista.length - 1] - lista[0])) * inreB : inreB / 2)
}
const farg = (i: number) => `var(--series-${(i % 8) + 1})`
const linje = (punkter: { ar: number; varde: number | null }[]) =>
  punkter
    .map((p, i) =>
      p.varde === null
        ? ''
        : `${i && punkter[i - 1].varde !== null && !props.brott?.includes(p.ar) ? 'L' : 'M'}${x(p.ar).toFixed(1)},${skala.value.y(p.varde).toFixed(1)}`,
    )
    .filter(Boolean)
    .join(' ')
// Ett värde utan grannar syns inte som linje, så det ritas som en punkt. Ett brott räknas som en saknad granne.
const ensamma = (punkter: { ar: number; varde: number | null }[]) =>
  punkter.filter(
    (p, i) =>
      p.varde !== null &&
      (punkter[i - 1]?.varde == null || !!props.brott?.includes(p.ar)) &&
      (punkter[i + 1]?.varde == null || !!props.brott?.includes(punkter[i + 1].ar)),
  )
// Den streckade linjen för ett brott står mitt emellan året före och brottsåret.
const brottslinjer = computed(() =>
  (props.brott ?? [])
    .filter((a) => ar.value.indexOf(a) > 0)
    .map((a) => ({ ar: a, x: (x(a) + x(ar.value[ar.value.indexOf(a) - 1])) / 2 })),
)

const aktivt = ref<number | null>(null)
function hover(e: MouseEvent) {
  const svg = (e.currentTarget as SVGSVGElement).getBoundingClientRect()
  const px = ((e.clientX - svg.left) / svg.width) * B
  aktivt.value = ar.value.reduce((bast, a) => (Math.abs(x(a) - px) < Math.abs(x(bast) - px) ? a : bast), ar.value[0])
}
const tooltip = computed(() =>
  aktivt.value === null
    ? null
    : props.serier
        .map((s, i) => ({ namn: s.namn, i, varde: s.punkter.find((p) => p.ar === aktivt.value)?.varde }))
        .filter((r) => r.varde !== undefined && r.varde !== null),
)
</script>

<template>
  <figure class="diagram">
    <ul v-if="serier.length > 1" class="forklaring" aria-label="Teckenförklaring">
      <li v-for="(s, i) in serier" :key="s.namn"><span class="prov" :style="{ background: farg(i) }" />{{ s.namn }}</li>
    </ul>
    <div class="yta">
      <svg :viewBox="`0 0 ${B} ${H}`" role="img" :aria-label="etikett" @mousemove="hover" @mouseleave="aktivt = null">
        <g class="rutnat">
          <template v-for="t in skala.ticks" :key="t">
            <line :x1="M.left" :x2="B - M.right" :y1="skala.y(t)" :y2="skala.y(t)" />
            <text :x="M.left - 8" :y="skala.y(t)" dy="0.32em" text-anchor="end">{{ axeltal(t, skala.steg) }}</text>
          </template>
          <text v-for="a in ar" :key="a" :x="x(a)" :y="H - 10" text-anchor="middle">{{ a }}</text>
        </g>
        <g v-for="b in brottslinjer" :key="`brott-${b.ar}`" class="brott" data-testid="metodbyte">
          <line :x1="b.x" :x2="b.x" :y1="M.top" :y2="H - M.bottom" />
          <text :x="b.x + 4" :y="M.top + 10">Metodbyte {{ b.ar }}</text>
        </g>
        <line v-if="aktivt !== null" class="markor" :x1="x(aktivt)" :x2="x(aktivt)" :y1="M.top" :y2="H - M.bottom" />
        <g v-for="(s, i) in serier" :key="s.namn">
          <path :d="linje(s.punkter)" :stroke="farg(i)" class="linje" />
          <circle
            v-for="p in ensamma(s.punkter)"
            :key="`ensam-${p.ar}`"
            :cx="x(p.ar)"
            :cy="skala.y(p.varde!)"
            r="2.5"
            :fill="farg(i)"
          />
          <circle
            v-for="p in s.punkter.filter((p) => p.ar === aktivt && p.varde !== null)"
            :key="p.ar"
            :cx="x(p.ar)"
            :cy="skala.y(p.varde!)"
            r="3.5"
            :fill="farg(i)"
          />
        </g>
      </svg>
      <div v-if="tooltip" class="tooltip" role="status" :style="{ left: `${(x(aktivt!) / B) * 100}%` }">
        <strong>{{ aktivt }}</strong>
        <div v-for="r in tooltip" :key="r.namn"><span class="prov" :style="{ background: farg(r.i) }" />{{ r.namn }}: {{ tal(r.varde!, enhet) }}</div>
        <div class="kalla">{{ kalla }}</div>
      </div>
    </div>
  </figure>
</template>

<style scoped>
.diagram {
  margin: 0;
}
.yta {
  position: relative;
}
svg {
  width: 100%;
  height: auto;
  display: block;
}
.rutnat line {
  stroke: var(--line);
  stroke-width: 1;
}
.rutnat text {
  font-size: 12px;
  fill: var(--ink-muted);
  font-variant-numeric: tabular-nums;
}
.linje {
  fill: none;
  stroke-width: 2;
}
.brott line {
  stroke: var(--ink-muted);
  stroke-width: 1;
  stroke-dasharray: 4 3;
}
.brott text {
  font-size: 11px;
  fill: var(--ink-muted);
}
.markor {
  stroke: var(--line-strong);
  stroke-width: 1;
}
.forklaring {
  list-style: none;
  display: flex;
  flex-wrap: wrap;
  gap: 4px 16px;
  margin: 0 0 8px;
  padding: 0;
  font-size: 12px;
  color: var(--ink-secondary);
}
.prov {
  display: inline-block;
  width: 12px;
  height: 2px;
  margin-right: 6px;
  vertical-align: middle;
}
.tooltip {
  position: absolute;
  top: 8px;
  transform: translateX(-50%);
  background: var(--surface-raised, var(--surface));
  border: 1px solid var(--line);
  border-radius: var(--radius);
  box-shadow: 0 2px 8px rgb(0 0 0 / 12%);
  padding: 6px 10px;
  font-size: 12px;
  pointer-events: none;
  white-space: nowrap;
  font-variant-numeric: tabular-nums;
}
.tooltip .kalla {
  color: var(--ink-muted);
  margin-top: 2px;
}
</style>
