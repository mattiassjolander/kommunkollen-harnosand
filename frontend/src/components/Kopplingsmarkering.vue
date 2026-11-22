<script setup lang="ts">
// Hur en koppling mellan två behandlingar har gjorts (ADR-0002, ADR-0003). En automatisk koppling
// är plattformens egen slutsats ur protokollen. En bekräftad koppling har granskats av en redaktör.
import { computed } from 'vue'
import type { Koppling } from '../api'

const props = defineProps<{ koppling: Koppling }>()

const TEXT = {
  automatisk: 'Automatisk koppling',
  forslag: 'Förslag, inte bekräftat',
  bekraftad: 'Bekräftad av redaktör',
  avvisad: 'Avvisad av redaktör',
} as const
const IKON = { automatisk: '⚙', forslag: '?', bekraftad: '✓', avvisad: '×' } as const

const grund = computed(() => {
  const { grund, underlag } = props.koppling
  if (grund === 'diarienummer') return `samma diarienummer ${underlag}`
  if (grund === 'motionstitel') return `samma motionstitel: ”${underlag}”`
  return `hänvisning i beslutsunderlaget: ”${underlag}”`
})
</script>

<template>
  <span class="markering" :class="koppling.status" data-testid="kopplingsstatus" :data-status="koppling.status">
    <span class="ikon" aria-hidden="true">{{ IKON[koppling.status] }}</span>
    <span>
      <strong>{{ TEXT[koppling.status] }}</strong> via {{ grund }}
    </span>
  </span>
</template>

<style scoped>
.markering {
  display: inline-flex;
  align-items: baseline;
  gap: 6px;
  font-size: 12px;
  color: var(--ink-secondary);
}
.ikon {
  display: inline-flex;
  width: 16px;
  height: 16px;
  align-items: center;
  justify-content: center;
  border: 1px solid currentColor;
  border-radius: 50%;
  font-size: 10px;
  flex: none;
}
.bekraftad .ikon {
  color: var(--status-good);
}
.forslag .ikon {
  color: var(--status-warning);
}
</style>
