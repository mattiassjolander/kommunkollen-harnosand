<script setup lang="ts">
// Markering för ett diarienummer som protokollet saknar och som har lästs ur föredragningslistan
// i kallelsen (docs/design.md, Säkerhetsmarkeringar). Läsaren kan fälla ut källan.
import type { Diarienummerkallelse } from '../api'

defineProps<{ kalla: Diarienummerkallelse }>()
</script>

<template>
  <details class="kallelse" data-testid="dnr-ur-kallelsen">
    <summary>
      <span class="ikon" aria-hidden="true">↗</span>
      ur kallelsen
    </summary>
    <p class="detaljer">
      Protokollet anger inget diarienummer. Numret står i föredragningslistan i
      <a :href="kalla.url" target="_blank" rel="noopener" data-testid="kallelselank"
        >{{ kalla.titel }}<template v-if="kalla.sida">, sidan {{ kalla.sida }}</template></a
      >.
    </p>
  </details>
</template>

<style scoped>
.kallelse {
  display: inline-block;
  font-size: 12px;
  color: var(--ink-secondary);
  vertical-align: baseline;
}
summary {
  cursor: pointer;
  display: inline-flex;
  align-items: center;
  gap: 6px;
  list-style: none;
  border: 1px dotted var(--line-strong);
  border-radius: var(--radius);
  padding: 0 6px;
}
summary::-webkit-details-marker {
  display: none;
}
.ikon {
  color: var(--ink-muted);
}
.detaljer {
  margin: 6px 0 0;
  padding: 8px 12px;
  border-left: 2px solid var(--line);
  max-width: 50ch;
  white-space: normal;
}
.detaljer a {
  color: var(--accent);
}
</style>
