<script setup lang="ts">
import { computed } from 'vue'
import type { Process, Processteg } from '../api'

// Processdiagrammet (#158): en bana per aktör, i den ordning aktörerna först förekommer, och stegen från vänster till
// höger i processens ordning. Övergångarna binder ihop stegen. Ett steg med flera övergångar är ett vägval (romb med
// kryss, som exklusiv gateway i BPMN) och övergångarna bär sina villkor. Ett steg utan övergång slutar i en
// sluthändelse. Det första steget och steg som ingen övergång leder till börjar i en starthändelse, märkt med stegets
// "när". En övergång bakåt ritas längs banans nederkant. Diagrammet ritar bara steg med citat: det som inte står i
// dokumenten finns inte med. Ett klick på ett steg väljer det i listan under diagrammet, som är textversionen.

const props = defineProps<{ p: Process }>()
const emit = defineEmits<{ valj: [id: number] }>()

const ETIKETT = 152 // banornas namn
const BOX_B = 176
const BOX_H = 88
const GLAPP = 72 // mellan stegen: händelser, vägval och lodräta pilar
const BANA = 140
const KANAL = 8 // avstånd från banans kant till pilarna som går längs den

const banor = computed(() => {
  const namn: string[] = []
  for (const s of props.p.steg) if (s.aktor && !namn.includes(s.aktor)) namn.push(s.aktor)
  return namn
})
const bredd = computed(() => ETIKETT + GLAPP + props.p.steg.length * (BOX_B + GLAPP))
const hojd = computed(() => banor.value.length * BANA)

const kol = (s: Processteg) => props.p.steg.indexOf(s)
const bana = (s: Processteg) => banor.value.indexOf(s.aktor ?? '')
const vanster = (s: Processteg) => ETIKETT + GLAPP + kol(s) * (BOX_B + GLAPP)
const hoger = (s: Processteg) => vanster(s) + BOX_B
const mitt = (s: Processteg) => bana(s) * BANA + BANA / 2
const topp = (b: number) => b * BANA
const id = (n: number) => props.p.steg.find((s) => s.id === n)!

const vagval = (s: Processteg) => s.overgangar.length > 1

/** Steg som någon övergång leder till. Övriga steg börjar i en egen starthändelse. */
const malen = computed(() => new Set(props.p.steg.flatMap((s) => s.overgangar.map((o) => o.till))))
const starter = computed(() => props.p.steg.filter((s, i) => i === 0 || !malen.value.has(s.id)))

const pilar = computed(() =>
  props.p.steg.flatMap((a) =>
    a.overgangar.map((o) => {
      const b = id(o.till)
      const ut = vagval(a) ? hoger(a) + 29 : hoger(a)
      const gA = hoger(a) + GLAPP / 2
      const gB = vanster(b) - GLAPP / 2
      const ya = mitt(a)
      const yb = mitt(b)
      let d: string
      let etikett: { x: number; y: number } | null = null
      if (kol(b) > kol(a)) {
        // Framåt: ut i glappet efter steget, längs överkanten av målets bana, ned i glappet före målet.
        const kanal = topp(bana(b)) + KANAL
        d =
          gA === gB && !o.villkor
            ? `M${ut} ${ya} H${gA} V${yb} H${vanster(b) - 2}`
            : `M${ut} ${ya} H${gA} V${kanal} H${gB} V${yb} H${vanster(b) - 2}`
        etikett = { x: gA + 6, y: kanal + 13 }
      } else {
        // Bakåt: längs nederkanten av stegets egen bana och in i målet underifrån eller ovanifrån. Varje kolumn har
        // bara ett steg, så den lodräta linjen i målets mitt korsar inget annat steg, och starthändelsen till vänster
        // om målet går fri.
        const kanal = topp(bana(a)) + BANA - KANAL
        const xb = vanster(b) + BOX_B / 2
        const in_ = kanal > yb ? yb + BOX_H / 2 + 2 : yb - BOX_H / 2 - 2
        d = `M${ut} ${ya} H${gA} V${kanal} H${xb} V${in_}`
        etikett = { x: xb + 6, y: kanal - 5 }
      }
      return { key: `${a.id}-${b.id}`, d, villkor: o.villkor, etikett }
    }),
  ),
)

const markeringar = (s: Processteg) =>
  [s.dokument_andrat ? 'Dokumentet har ändrats' : null, s.motstridigheter.length ? 'Motstridighet' : null].filter(
    (m): m is string => !!m,
  )
const namn = (s: Processteg) =>
  [`Steg ${s.ordning}, ${s.aktor}: ${s.vad}`, s.nar, ...markeringar(s)].filter(Boolean).join('. ')
const pil = computed(() => `pil-${props.p.id}`)
</script>

<template>
  <figure class="diagram" data-testid="processdiagram">
    <div class="rull">
      <svg :width="bredd" :height="hojd" :viewBox="`0 0 ${bredd} ${hojd}`" role="group"
           :aria-label="`Processdiagram: ${p.namn}, ${banor.length} aktörer och ${p.steg.length} steg`">
        <defs>
          <marker :id="pil" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="7" markerHeight="7" orient="auto">
            <path d="M1 1L9 5L1 9z" class="pilhuvud" />
          </marker>
        </defs>
        <g v-for="(a, i) in banor" :key="a" data-testid="bana">
          <rect :x="0" :y="topp(i)" :width="bredd" :height="BANA" class="banyta" :class="{ udda: i % 2 }" />
          <foreignObject :x="8" :y="topp(i)" :width="ETIKETT - 16" :height="BANA">
            <div class="banetikett" lang="sv">{{ a }}</div>
          </foreignObject>
        </g>
        <line :x1="ETIKETT" y1="0" :x2="ETIKETT" :y2="hojd" class="skiljelinje" />

        <path v-for="k in pilar" :key="k.key" :d="k.d" class="pil" :marker-end="`url(#${pil})`" />
        <template v-for="k in pilar" :key="`v${k.key}`">
          <text v-if="k.villkor && k.etikett" :x="k.etikett.x" :y="k.etikett.y" class="villkor"
                data-testid="villkor">{{ k.villkor }}</text>
        </template>

        <g v-for="s in starter" :key="`start${s.id}`" data-testid="start">
          <circle :cx="vanster(s) - 18" :cy="mitt(s)" r="9" class="handelse" />
          <line :x1="vanster(s) - 9" :y1="mitt(s)" :x2="vanster(s) - 2" :y2="mitt(s)" class="pil"
                :marker-end="`url(#${pil})`" />
          <text v-if="s.ordning > 1 && s.nar" :x="vanster(s) - 27" :y="topp(bana(s)) + BANA - 12" class="villkor">
            {{ s.nar.length > 34 ? `${s.nar.slice(0, 33)}…` : s.nar }}
            <title>{{ s.nar }}</title>
          </text>
        </g>

        <g v-for="s in p.steg" :key="s.id">
          <template v-if="vagval(s)">
            <line :x1="hoger(s)" :y1="mitt(s)" :x2="hoger(s) + 7" :y2="mitt(s)" class="pil" />
            <g data-testid="vagval">
              <path :d="`M${hoger(s) + 18} ${mitt(s) - 11} l11 11 l-11 11 l-11 -11z`" class="handelse" />
              <path :d="`M${hoger(s) + 14} ${mitt(s) - 4} l8 8 m0 -8 l-8 8`" class="kryss" />
            </g>
          </template>
          <g v-else-if="!s.overgangar.length" data-testid="slut">
            <line :x1="hoger(s)" :y1="mitt(s)" :x2="hoger(s) + 9" :y2="mitt(s)" class="pil" />
            <circle :cx="hoger(s) + 18" :cy="mitt(s)" r="9" class="handelse slut" />
          </g>
          <foreignObject :x="vanster(s)" :y="mitt(s) - BOX_H / 2" :width="BOX_B" :height="BOX_H">
            <button type="button" class="steg" :aria-label="namn(s)" data-testid="diagramsteg"
                    @click="emit('valj', s.id)">
              <span class="vad">{{ s.vad }}</span>
              <span v-if="s.nar" class="nar">{{ s.nar }}</span>
              <span v-for="m in markeringar(s)" :key="m" class="markering" data-testid="diagrammarkering">! {{ m }}</span>
            </button>
          </foreignObject>
        </g>
      </svg>
    </div>
    <figcaption class="not">
      En bana per aktör. Välj ett steg för citat och källa i listan under diagrammet.
    </figcaption>
  </figure>
</template>

<style scoped>
.diagram {
  margin: 0 0 16px;
}
.rull {
  overflow-x: auto;
  border: 1px solid var(--line);
  border-radius: var(--radius);
  background: var(--surface);
}
svg {
  display: block;
}
.banyta {
  fill: var(--surface);
  stroke: var(--line);
  stroke-width: 1;
}
.banyta.udda {
  fill: var(--page);
}
.skiljelinje {
  stroke: var(--line-strong);
}
.banetikett {
  height: 100%;
  display: flex;
  align-items: center;
  font-size: 13px;
  font-weight: 600;
  color: var(--ink-secondary);
  overflow-wrap: break-word;
  hyphens: auto;
}
.pil {
  fill: none;
  stroke: var(--ink-secondary);
  stroke-width: 1.5;
}
.pilhuvud {
  fill: var(--ink-secondary);
}
.handelse {
  fill: var(--surface-raised);
  stroke: var(--ink-secondary);
  stroke-width: 1.5;
}
.handelse.slut {
  stroke-width: 3;
}
.kryss {
  stroke: var(--ink-secondary);
  stroke-width: 1.5;
}
.villkor {
  font-size: 11px;
  fill: var(--ink-secondary);
}
.steg {
  all: unset;
  box-sizing: border-box;
  width: 100%;
  height: 100%;
  display: flex;
  flex-direction: column;
  gap: 2px;
  padding: 6px 8px;
  border: 1px solid var(--line-strong);
  border-radius: var(--radius);
  background: var(--surface-raised);
  color: var(--ink);
  font-size: 12px;
  line-height: 1.3;
  cursor: pointer;
  overflow: hidden;
}
.steg:hover {
  border-color: var(--accent);
}
.steg:focus-visible {
  outline: 2px solid var(--accent);
  outline-offset: 1px;
}
.vad {
  display: -webkit-box;
  -webkit-box-orient: vertical;
  -webkit-line-clamp: 3;
  line-clamp: 3;
  overflow: hidden;
}
.nar {
  font-weight: 600;
  color: var(--ink-secondary);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.markering {
  font-size: 11px;
  font-weight: 600;
  color: var(--ink-secondary);
}
.not {
  font-size: 12px;
  color: var(--ink-muted);
  margin: 4px 0 0;
}
</style>
