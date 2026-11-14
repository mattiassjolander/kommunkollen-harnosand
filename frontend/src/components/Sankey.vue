<script setup lang="ts">
// Sankey med tre kolumner: inflöden → mittnod → utflöden. På kommunnivån är mittnoden Kommunens
// intäkter, i en fördjupning ett verksamhetsområdes bruttokostnad.
// Noder och flöden beräknas i backend. Här görs bara layouten: höjd proportionell mot belopp.
import { computed, ref } from 'vue'
import type { Flode, Flodesnod } from '../api'
import { procentforandring, tal, visningsskala } from '../format'

const props = defineProps<{
  noder: Flodesnod[]
  floden: Flode[]
  valt: Flode | null
  /** Noder som går att fördjupa (verksamhetsområden på kommunnivån). */
  fordjupbara?: string[]
}>()
const emit = defineEmits<{ valj: [Flode]; fordjupa: [string] }>()
const kanFordjupas = (id: string) => props.fordjupbara?.includes(id) ?? false

const B = 1120
const H = 560
const NODB = 12
const MELLANRUM = 18 // plats för en etikettrad mellan noderna
const X = { in: 340, mitt: B / 2 - NODB / 2, ut: B - 310 - NODB }
const TOPP = 28 // plats för mittnodens etikett

const skala = visningsskala('tkr')
const mnkr = (tkr: number) => tal(tkr * skala.faktor, skala.enhet)

interface Placerad extends Flodesnod {
  x: number
  y: number
  h: number
}

const layout = computed(() => {
  const sidor = { in: props.noder.filter((n) => n.sida === 'in'), ut: props.noder.filter((n) => n.sida === 'ut') }
  const mitt = props.noder.find((n) => n.sida === 'mitt')!
  const total = mitt?.belopp ?? 1
  // Samma skala på båda sidor: den sida som har flest noder (mest mellanrum) bestämmer.
  const k = Math.min(...(['in', 'ut'] as const).map((s) => (H - (sidor[s].length - 1) * MELLANRUM) / total))
  const placerade = new Map<string, Placerad>()
  for (const s of ['in', 'ut'] as const) {
    const hojd = total * k + (sidor[s].length - 1) * MELLANRUM
    let y = (H - hojd) / 2
    for (const n of sidor[s]) {
      const h = Math.max(1, n.belopp * k)
      placerade.set(n.id, { ...n, x: X[s], y, h })
      y += h + MELLANRUM
    }
  }
  const mittH = total * k
  if (mitt) placerade.set(mitt.id, { ...mitt, x: X.mitt, y: (H - mittH) / 2, h: mittH })

  // Flödenas band. I mittnoden staplas de i samma ordning som noderna på respektive sida.
  const mittY = { in: (H - mittH) / 2, ut: (H - mittH) / 2 }
  const band = props.floden.map((f) => {
    const inat = f.till === mitt.id
    const yttre = placerade.get(inat ? f.fran : f.till)!
    const inre = placerade.get(mitt.id)!
    const h = Math.max(1, f.belopp * k)
    const sida = inat ? 'in' : 'ut'
    const yInre = mittY[sida]
    mittY[sida] += h
    const [x0, y0, x1, y1] = inat
      ? [yttre.x + NODB, yttre.y, inre.x, yInre]
      : [inre.x + NODB, yInre, yttre.x, yttre.y]
    const mx = (x0 + x1) / 2
    const d = `M${x0},${y0} C${mx},${y0} ${mx},${y1} ${x1},${y1} L${x1},${y1 + h} C${mx},${y1 + h} ${mx},${y0 + h} ${x0},${y0 + h} Z`
    return { f, d, id: inat ? f.fran : f.till, titel: yttre.titel }
  })
  // Förändringen mot jämförelseåret visas vid nodens etikett.
  const forandring = new Map(
    props.floden.map((f) => [f.till === mitt.id ? f.fran : f.till, f.jamforelse] as const),
  )
  return { noder: [...placerade.values()], band, forandring }
})

function forandringstext(id: string): string | null {
  const j = layout.value.forandring.get(id)
  if (!j) return null
  if (j.belopp === null) return 'ny'
  return j.procent === null ? null : procentforandring(j.procent)
}

const hovrad = ref<string | null>(null)
const aktivt = (id: string) => hovrad.value === id || (props.valt && (props.valt.fran === id || props.valt.till === id))
</script>

<template>
  <svg :viewBox="`0 -${TOPP} ${B} ${H + TOPP}`" class="sankey" role="group" aria-label="Sankeydiagram över kommunens ekonomiska flöden">
    <g class="band">
      <path
        v-for="b in layout.band"
        :key="b.id"
        :d="b.d"
        :class="{ aktiv: aktivt(b.id), ut: b.f.fran === 'kommunen' }"
        :data-flode="b.id"
        tabindex="0"
        role="button"
        :aria-label="`${b.titel}: ${mnkr(b.f.belopp)}`"
        :aria-pressed="!!valt && (valt.fran === b.id || valt.till === b.id)"
        @mouseenter="hovrad = b.id"
        @mouseleave="hovrad = null"
        @click="emit('valj', b.f)"
        @keydown.enter.prevent="emit('valj', b.f)"
        @keydown.space.prevent="emit('valj', b.f)"
      >
        <title>{{ b.titel }}: {{ mnkr(b.f.belopp) }}</title>
      </path>
    </g>
    <g v-for="n in layout.noder" :key="n.id" class="nod" :data-nod="n.id">
      <rect :x="n.x" :y="n.y" :width="NODB" :height="n.h" rx="2" :class="n.sida" />
      <text
        v-if="n.sida === 'mitt'"
        :x="n.x + NODB / 2"
        :y="n.y - 10"
        text-anchor="middle"
        class="etikett stark"
      >
        {{ n.titel }} {{ mnkr(n.belopp) }}
      </text>
      <text
        v-else
        :x="n.sida === 'in' ? n.x - 8 : n.x + NODB + 8"
        :y="n.y + n.h / 2"
        :text-anchor="n.sida === 'in' ? 'end' : 'start'"
        dominant-baseline="middle"
        class="etikett"
        :class="{ fordjupbar: kanFordjupas(n.id) }"
        :role="kanFordjupas(n.id) ? 'link' : undefined"
        :tabindex="kanFordjupas(n.id) ? 0 : undefined"
        :aria-label="kanFordjupas(n.id) ? `Visa kostnadsslag för ${n.titel}` : undefined"
        :data-fordjupa="kanFordjupas(n.id) ? n.id : undefined"
        @click="kanFordjupas(n.id) && emit('fordjupa', n.id)"
        @keydown.enter.prevent="kanFordjupas(n.id) && emit('fordjupa', n.id)"
      >
        <tspan class="namn">{{ n.titel }}</tspan><tspan v-if="kanFordjupas(n.id)" class="pil"> ›</tspan>
        <tspan class="belopp tal" dx="4">{{ mnkr(n.belopp) }}</tspan>
        <tspan v-if="forandringstext(n.id)" class="forandring tal" dx="6" data-testid="nodforandring">
          {{ forandringstext(n.id) }}
        </tspan>
      </text>
    </g>
  </svg>
</template>

<style scoped>
.sankey {
  width: 100%;
  height: auto;
  display: block;
}
.band path {
  fill: var(--series-1);
  opacity: 0.28;
  cursor: pointer;
  transition: opacity 120ms;
}
.band path.ut {
  fill: var(--accent);
  opacity: 0.22;
}
.band path.aktiv,
.band path:focus-visible {
  opacity: 0.7;
  outline: none;
}
.nod rect {
  fill: var(--ink-secondary);
}
.nod rect.mitt {
  fill: var(--ink);
}
.etikett {
  font-size: 12px;
  fill: var(--ink);
}
.etikett.stark {
  font-weight: 600;
}
.belopp,
.forandring {
  fill: var(--ink-muted);
}
.fordjupbar {
  cursor: pointer;
}
.fordjupbar .namn {
  text-decoration: underline;
  text-decoration-color: var(--line-strong);
  text-underline-offset: 2px;
}
.fordjupbar:hover .namn,
.fordjupbar:focus-visible .namn {
  fill: var(--accent);
  text-decoration-color: var(--accent);
}
.fordjupbar:focus-visible {
  outline: none;
}
.pil {
  fill: var(--accent);
}
</style>
