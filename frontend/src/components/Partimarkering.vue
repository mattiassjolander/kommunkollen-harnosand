<script setup lang="ts">
// Parti som protokollet anger det: förkortningen, med partiets färg som en liten prick bredvid.
// Färgen bär aldrig information ensam (design.md, Partifärger).
import { computed } from 'vue'
import { parti as partitext } from '../format'

const props = defineProps<{ parti: string | null }>()

const KANDA = ['S', 'M', 'SD', 'C', 'V', 'KD', 'L', 'MP']
const farg = computed(() =>
  props.parti && KANDA.includes(props.parti) ? `var(--parti-${props.parti.toLowerCase()})` : null,
)
const vanligt = computed(() => props.parti !== null && props.parti !== '-')
</script>

<template>
  <span class="parti" :class="{ saknas: props.parti === null }" data-testid="parti" :data-parti="props.parti ?? ''">
    <span v-if="vanligt" class="prick" :style="farg ? { background: farg } : undefined" aria-hidden="true" />{{
      partitext(props.parti)
    }}
  </span>
</template>

<style scoped>
.parti {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  white-space: nowrap;
}
.prick {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: var(--ink-muted);
  box-shadow: 0 0 0 1px var(--line-strong);
  flex: none;
}
.saknas {
  color: var(--ink-muted);
  font-style: italic;
}
</style>
