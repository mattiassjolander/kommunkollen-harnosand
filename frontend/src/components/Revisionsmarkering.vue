<script setup lang="ts">
// ↻ vid ett värde som källan har reviderat (docs/design.md). Tooltipen visar tidigare och nytt
// värde, när ändringen gjordes i plattformen och vilken källa som reviderade.
import { ref } from 'vue'
import { tabelldatum, tal } from '../format'
import type { Revision } from '../api'

const props = defineProps<{ revision: Revision; nytt: number | null; enhet: string }>()
const oppen = ref(false)
const text = () =>
  `Reviderat av ${props.revision.kalla}. Tidigare ${tal(props.revision.tidigare, props.enhet)}, nu ${tal(
    props.nytt,
    props.enhet,
  )}. Ändrat ${tabelldatum(props.revision.andrad)}.`
</script>

<template>
  <span
    class="reviderad"
    tabindex="0"
    role="img"
    :aria-label="text()"
    data-testid="reviderad"
    @mouseenter="oppen = true"
    @mouseleave="oppen = false"
    @focus="oppen = true"
    @blur="oppen = false"
  >
    ↻
    <span v-if="oppen" class="tips" role="tooltip" data-testid="revisionstips">
      <strong>Reviderat av källan</strong>
      <span>Tidigare: <span class="tal">{{ tal(revision.tidigare, enhet) }}</span></span>
      <span>Nytt: <span class="tal">{{ tal(nytt, enhet) }}</span></span>
      <span class="liten">Ändrat {{ tabelldatum(revision.andrad) }} · {{ revision.kalla }}</span>
    </span>
  </span>
</template>

<style scoped>
.reviderad {
  position: relative;
  display: inline-block;
  margin-left: 4px;
  color: var(--accent);
  cursor: help;
  font-weight: 600;
}
.reviderad:focus-visible {
  outline: 2px solid var(--accent);
  outline-offset: 2px;
  border-radius: 2px;
}
.tips {
  position: absolute;
  z-index: 10;
  right: 0;
  top: calc(100% + 4px);
  background: var(--surface-raised);
  border: 1px solid var(--line);
  border-radius: var(--radius);
  box-shadow: var(--shadow-float);
  padding: 8px 12px;
  display: flex;
  flex-direction: column;
  gap: 2px;
  white-space: nowrap;
  text-align: left;
  font-weight: 400;
  color: var(--ink);
}
.liten {
  font-size: 12px;
  color: var(--ink-muted);
}
</style>
