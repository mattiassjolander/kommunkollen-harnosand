<script setup lang="ts">
// En avvikelse med länk till källan efter texten, när den har en (#121): kallelsens avvikelser
// länkar till kallelsen på punktens sida.
import type { Avvikelse } from '../api'

defineProps<{ avvikelse: Avvikelse }>()
</script>

<template>
  {{ avvikelse.text }}
  <a
    v-if="avvikelse.lank"
    :href="avvikelse.lank.url"
    :title="avvikelse.lank.titel"
    class="lank"
    target="_blank"
    rel="noopener"
    data-testid="avvikelselank"
    >Öppna kallelsen<template v-if="avvikelse.lank.sida">, sidan {{ avvikelse.lank.sida }}</template></a
  >
</template>

<style scoped>
.lank {
  color: var(--accent);
  white-space: nowrap;
}
</style>
