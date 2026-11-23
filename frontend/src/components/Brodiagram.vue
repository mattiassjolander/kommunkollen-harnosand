<script setup lang="ts">
// Brodiagram (vattenfall) som bygger upp en summa steg för steg, liggande så att långa namn får plats
// även i mobilbredd. Färgerna följer den divergerande skalan i docs/design.md: ett tillskott är blått,
// ett avdrag rött ("lägre", inte "dåligt") och summan grå. Tecken och text bär informationen.
import { computed, ref } from 'vue'
import { tal } from '../format'

export interface Brosteg {
  id: string
  titel: string
  /** I visningsenheten. null = uppgift saknas. */
  varde: number | null
  /** 'summa' ritas från noll, övriga från föregående delsumma. */
  typ: 'del' | 'summa'
  kalla: string
  /** T.ex. "Summerat av Kommunkollen ur SCB". */
  markering?: string
}

const props = defineProps<{ steg: Brosteg[]; enhet: string; period: string }>()

// Varje stegs start och slut på skalan.
const staplar = computed(() => {
  let lopande = 0
  return props.steg.map((s) => {
    const v = s.varde ?? 0
    const fran = s.typ === 'summa' ? 0 : lopande
    const till = s.typ === 'summa' ? v : lopande + v
    if (s.typ !== 'summa') lopande = till
    return { ...s, fran, till }
  })
})
const doman = computed(() => {
  const alla = staplar.value.flatMap((s) => [s.fran, s.till])
  const min = Math.min(0, ...alla)
  const max = Math.max(0, ...alla)
  return { min, spann: max - min || 1 }
})
const pos = (x: number) => ((x - doman.value.min) / doman.value.spann) * 100

const tecken = (v: number) => (v > 0 ? '+' : v < 0 ? '−' : '±')
function etikett(s: Brosteg): string {
  if (s.varde === null) return 'Uppgift saknas'
  return s.typ === 'summa' ? tal(s.varde, props.enhet) : `${tecken(s.varde)}${tal(Math.abs(s.varde), props.enhet)}`
}

const aktiv = ref<string | null>(null)
</script>

<template>
  <div class="bro" role="list" :aria-label="`Brodiagram ${period}, ${enhet}`" @mouseleave="aktiv = null">
    <div
      v-for="s in staplar"
      :key="s.id"
      class="rad"
      :class="{ summa: s.typ === 'summa', aktiv: aktiv === s.id }"
      role="listitem"
      data-testid="brosteg"
      :data-steg="s.id"
      @mouseenter="aktiv = s.id"
    >
      <span class="titel">
        {{ s.typ === 'summa' ? '=' : '' }} {{ s.titel }}
        <span v-if="s.markering" class="markering" data-testid="bromarkering">{{ s.markering }}</span>
      </span>
      <span class="spar" aria-hidden="true">
        <span class="noll" :style="{ left: `${pos(0)}%` }" />
        <span
          v-if="s.varde !== null"
          class="stapel"
          :class="s.typ === 'summa' ? 'neutral' : s.varde < 0 ? 'lagre' : 'hogre'"
          :style="{ left: `${pos(Math.min(s.fran, s.till))}%`, width: `${Math.max(pos(Math.max(s.fran, s.till)) - pos(Math.min(s.fran, s.till)), 0.4)}%` }"
        />
      </span>
      <span class="varde tal" :class="{ saknas: s.varde === null }" data-testid="brovarde">{{ etikett(s) }}</span>
      <span v-if="aktiv === s.id" class="tips" role="tooltip">
        <strong>{{ s.titel }} {{ period }}</strong>
        <span class="tal">{{ etikett(s) }}</span>
        <span class="tipskalla">{{ s.kalla }}</span>
      </span>
    </div>
  </div>
</template>

<style scoped>
.bro {
  display: flex;
  flex-direction: column;
  gap: 6px;
  font-size: 13px;
}
.rad {
  position: relative;
  display: grid;
  grid-template-columns: minmax(0, 15rem) minmax(80px, 1fr) auto;
  align-items: center;
  gap: 4px 12px;
  padding: 2px 0;
}
.rad.summa {
  border-top: 1px solid var(--line-strong);
  padding-top: 8px;
  font-weight: 600;
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
.markering {
  display: block;
  font-size: 11px;
  font-weight: 400;
  color: var(--ink-muted);
}
.spar {
  position: relative;
  height: 18px;
}
.noll {
  position: absolute;
  top: -3px;
  bottom: -3px;
  border-left: 1px solid var(--line-strong);
}
.stapel {
  position: absolute;
  top: 2px;
  bottom: 2px;
  border-radius: 2px;
}
.stapel.hogre {
  background: var(--diverg-hogre);
}
.stapel.lagre {
  background: var(--diverg-lagre);
}
.stapel.neutral {
  background: var(--ink-muted);
}
.varde {
  text-align: right;
  white-space: nowrap;
}
.saknas {
  color: var(--ink-muted);
  font-style: italic;
}
.tips {
  position: absolute;
  right: 0;
  bottom: 100%;
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
  font-weight: 400;
}
.tipskalla {
  font-size: 12px;
  color: var(--ink-muted);
}
</style>
