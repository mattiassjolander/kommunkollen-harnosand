<script setup lang="ts">
// Värmekarta över revideringarna mellan SKR:s cirkulär (#161). En rad per par av på varandra följande cirkulär,
// en kolumn per prognosår. Rutan visar ändringen i mnkr mot föregående cirkulär och har procent i
// verktygstipset. Färgen följer den divergerande skalan i docs/design.md: en höjning är blå och en sänkning röd
// ("lägre", inte "dåligt"), och färgen blir starkare ju större ändringen är. Noll är ytans färg. Tecknet och
// talet bär informationen, så kartan är en riktig tabell som skärmläsare kan läsa.
import { computed, ref } from 'vue'
import { datum, tal, talforandring } from '../format'
import { andring, prognosAren, SUMMARAD, type Andring, type Revidering } from '../revideringar'

const props = defineProps<{ revideringar: Revidering[]; valdRad?: number; valtAr?: number }>()
const emit = defineEmits<{ valj: [rad: number, ar: number] }>()

const ar = computed(() => prognosAren(props.revideringar))
const celler = computed(() =>
  props.revideringar.map((r) => ar.value.map((a) => andring(r.fran, r.till, SUMMARAD, a))),
)
const storsta = computed(() => Math.max(1, ...celler.value.flat().map((c) => Math.abs(c?.tkr ?? 0))))

const mnkr = (tkr: number) => talforandring(Math.round(tkr / 100) / 10 || 0, 'mnkr')
const procent = new Intl.NumberFormat('sv-SE', { minimumFractionDigits: 2, maximumFractionDigits: 2, signDisplay: 'exceptZero' })
const pct = (c: Andring) => (c.procent === null ? 'procent saknas' : `${procent.format(c.procent)} %`)
const fran = (tkr: number) => tal(tkr / 1000, 'mnkr')

/** Andelen färg i rutan: 0 för ingen ändring, annars 10–60 % efter storleken. Ink läses mot båda ändarna. */
function farg(c: Andring | null) {
  if (!c || Math.round(c.tkr / 100) === 0) return undefined
  const andel = Math.round(10 + 50 * Math.min(1, Math.abs(c.tkr) / storsta.value))
  const ton = c.tkr > 0 ? 'var(--diverg-hogre)' : 'var(--diverg-lagre)'
  return { background: `color-mix(in srgb, ${ton} ${andel}%, var(--surface))` }
}

const etikett = (r: Revidering) => `${r.fran.cirkular} → ${r.till.cirkular}`

// Verktygstipset ligger utanför rullrutan så att det inte klipps, och placeras vid rutan.
const ram = ref<HTMLElement | null>(null)
const tips = ref<{ i: number; a: number; x: number; y: number } | null>(null)
function visa(e: Event, i: number, a: number) {
  const cell = (e.currentTarget as HTMLElement).getBoundingClientRect()
  const yta = ram.value!.getBoundingClientRect()
  tips.value = { i, a, x: cell.left - yta.left + cell.width / 2, y: cell.top - yta.top }
}
const tipsCell = computed(() => (tips.value ? celler.value[tips.value.i]?.[ar.value.indexOf(tips.value.a)] ?? null : null))
const tipsRev = computed(() => (tips.value ? props.revideringar[tips.value.i] : null))
</script>

<template>
  <div ref="ram" class="karta" @mouseleave="tips = null">
    <div class="rulla">
      <table class="tabell" data-testid="revideringskarta">
        <caption class="dold">
          Ändring av summa intäkter inklusive avräkning och fastighetsavgift mot föregående cirkulär, i mnkr, per
          prognosår
        </caption>
        <thead>
          <tr>
            <th scope="col">Cirkulär</th>
            <th v-for="a in ar" :key="a" scope="col" class="num">{{ a }}</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="(r, i) in revideringar" :key="etikett(r)" :data-revidering="etikett(r)">
            <th scope="row">
              <span class="par">{{ etikett(r) }}</span>
              <span class="datum">{{ datum(r.till.publicerad) }}</span>
            </th>
            <td
              v-for="(a, j) in ar"
              :key="a"
              class="num cell"
              :class="{ vald: valdRad === i && valtAr === a, tom: !celler[i][j] }"
              :style="farg(celler[i][j])"
              :data-ar="a"
              :tabindex="celler[i][j] ? 0 : undefined"
              @mouseenter="visa($event, i, a)"
              @focus="visa($event, i, a)"
              @blur="tips = null"
              @click="celler[i][j] && emit('valj', i, a)"
              @keydown.enter.prevent="celler[i][j] && emit('valj', i, a)"
            >
              <template v-if="celler[i][j]">
                {{ mnkr(celler[i][j]!.tkr) }}<span class="dold">, {{ pct(celler[i][j]!) }}</span>
              </template>
              <template v-else><span aria-hidden="true">–</span><span class="dold">Prognos saknas</span></template>
            </td>
          </tr>
        </tbody>
      </table>
    </div>
    <div
      v-if="tips && tipsRev"
      class="tips"
      role="tooltip"
      data-testid="revideringstips"
      :style="{ left: `${tips.x}px`, top: `${tips.y}px` }"
    >
      <strong>{{ tips.a }}, {{ etikett(tipsRev) }}</strong>
      <template v-if="tipsCell">
        <span class="tal">{{ mnkr(tipsCell.tkr) }} ({{ pct(tipsCell) }})</span>
        <span class="tal detalj">Från {{ fran(tipsCell.fran) }} till {{ fran(tipsCell.till) }}</span>
      </template>
      <span v-else class="detalj">Året finns inte i båda prognoserna</span>
      <span class="kalla">SKR, cirkulär {{ tipsRev.fran.cirkular }} och {{ tipsRev.till.cirkular }}</span>
    </div>
    <p class="forklaring">
      <span class="post"><span class="prov hogre" aria-hidden="true" /> höjd prognos</span>
      <span class="post"><span class="prov lagre" aria-hidden="true" /> sänkt prognos</span>
      <span>Starkare färg betyder större ändring. Välj en ruta för att se vad som drev ändringen.</span>
    </p>
  </div>
</template>

<style scoped>
.karta {
  position: relative;
  font-size: 13px;
}
.rulla {
  overflow-x: auto;
}
.tabell {
  border-collapse: separate;
  border-spacing: 2px;
  width: 100%;
}
.tabell th {
  text-align: left;
  font-weight: 400;
  padding: 4px 8px;
  white-space: nowrap;
}
.tabell thead th {
  color: var(--ink-secondary);
}
.tabell tbody th {
  position: sticky;
  left: 0;
  background: var(--surface);
  z-index: 1;
}
.par {
  display: block;
  font-variant-numeric: tabular-nums;
}
.datum {
  display: block;
  font-size: 12px;
  color: var(--ink-muted);
}
.num {
  text-align: right;
  font-variant-numeric: tabular-nums;
  white-space: nowrap;
}
.cell {
  padding: 8px;
  min-width: 4.5rem;
  border-radius: 2px;
  background: var(--surface);
  color: var(--ink);
  border: 1px solid var(--line);
  cursor: pointer;
}
.cell.tom {
  color: var(--ink-muted);
  cursor: default;
}
.cell:focus-visible {
  outline: 2px solid var(--accent);
  outline-offset: 1px;
}
.cell.vald {
  border: 2px solid var(--ink);
}
.tips {
  position: absolute;
  transform: translate(-50%, calc(-100% - 6px));
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
.tal {
  font-variant-numeric: tabular-nums;
}
.detalj {
  color: var(--ink-secondary);
}
.kalla {
  font-size: 12px;
  color: var(--ink-muted);
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
.prov.hogre {
  background: var(--diverg-hogre);
}
.prov.lagre {
  background: var(--diverg-lagre);
}
.dold {
  position: absolute;
  width: 1px;
  height: 1px;
  overflow: hidden;
  clip: rect(0 0 0 0);
  white-space: nowrap;
}
</style>
