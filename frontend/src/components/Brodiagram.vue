<script setup lang="ts">
// Brodiagram (vattenfall) som bygger upp en summa steg för steg, liggande så att långa namn får plats
// även i mobilbredd. Med `staende` står stegen som kolumner när diagrammet får plats, och ligger med en rad
// per steg på smal skärm (#147). Färgerna följer den divergerande skalan i docs/design.md: ett tillskott är blått,
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

const props = defineProps<{ steg: Brosteg[]; enhet: string; period: string; staende?: boolean }>()

// Varje stegs start och slut på skalan.
const staplar = computed(() => {
  let lopande = 0
  return props.steg.map((s) => {
    const v = s.varde ?? 0
    const fran = s.typ === 'summa' ? 0 : lopande
    const till = s.typ === 'summa' ? v : lopande + v
    // En summa mitt i diagrammet är också startpunkten för stegen efter den.
    lopande = till
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
// Stapelns start och längd på skalan, som CSS-variabler: liggande blir de left och width, stående bottom och height.
const stapelstil = (s: { fran: number; till: number }) => ({
  '--start': `${pos(Math.min(s.fran, s.till))}%`,
  '--langd': `${Math.max(pos(Math.max(s.fran, s.till)) - pos(Math.min(s.fran, s.till)), 0.4)}%`,
})

const tecken = (v: number) => (v > 0 ? '+' : v < 0 ? '−' : '±')
function etikett(s: Brosteg): string {
  if (s.varde === null) return 'Uppgift saknas'
  return s.typ === 'summa' ? tal(s.varde, props.enhet) : `${tecken(s.varde)}${tal(Math.abs(s.varde), props.enhet)}`
}

const aktiv = ref<string | null>(null)
</script>

<template>
  <div class="behallare" :class="{ staende }">
  <div class="bro" role="list" :aria-label="`Brodiagram ${period}, ${enhet}`" @mouseleave="aktiv = null">
    <div
      v-for="(s, i) in staplar"
      :key="s.id"
      class="rad"
      :class="{ summa: s.typ === 'summa', aktiv: aktiv === s.id, borjan: i < staplar.length / 2 }"
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
        <span class="noll" :style="{ '--noll': `${pos(0)}%` }" />
        <span
          v-if="s.varde !== null"
          class="stapel"
          :class="s.typ === 'summa' ? 'neutral' : s.varde < 0 ? 'lagre' : 'hogre'"
          :style="stapelstil(s)"
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
  </div>
</template>

<style scoped>
.behallare {
  container-type: inline-size;
}
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
  left: var(--noll);
  border-left: 1px solid var(--line-strong);
}
.stapel {
  position: absolute;
  top: 2px;
  bottom: 2px;
  left: var(--start);
  width: var(--langd);
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
/* Stående kolumner när diagrammet får plats. */
@container (min-width: 820px) {
  .staende .bro {
    flex-direction: row;
    align-items: stretch;
    gap: 4px;
  }
  .staende .rad {
    flex: 1 1 0;
    min-width: 0;
    grid-template-columns: minmax(0, 1fr);
    grid-template-rows: auto 220px auto;
    grid-template-areas: 'varde' 'spar' 'titel';
    gap: 4px;
    padding: 0;
  }
  .staende .rad.summa {
    border-top: 0;
    padding-top: 0;
  }
  .staende .titel {
    grid-area: titel;
    font-size: 11px;
    text-align: center;
    overflow-wrap: anywhere;
    hyphens: auto;
  }
  .staende .spar {
    grid-area: spar;
    grid-column: auto;
    grid-row: auto;
    height: auto;
    align-self: stretch;
  }
  .staende .varde {
    grid-area: varde;
    align-self: end;
    font-size: 11px;
    text-align: center;
    white-space: normal;
  }
  .staende .noll {
    top: auto;
    left: -2px;
    right: -2px;
    bottom: var(--noll);
    border-left: 0;
    border-top: 1px solid var(--line-strong);
  }
  .staende .stapel {
    top: auto;
    left: 15%;
    width: 70%;
    bottom: var(--start);
    height: var(--langd);
  }
  .staende .borjan .tips {
    left: 0;
    right: auto;
  }
}
</style>
