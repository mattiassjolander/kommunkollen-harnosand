<script setup lang="ts">
// Ikonen för förändringen i placering mot föregående år (#177): ▲ för ett lägre platsnummer, ▼ för ett högre och =
// för samma. Färgerna följer den divergerande skalan i docs/design.md. Texten bredvid säger samma sak, så ikonen är
// dold för skärmläsare och färgen bär aldrig betydelse ensam. Ingen ikon när en jämförelse saknas.
import { computed } from 'vue'

const props = defineProps<{ andring: number | null }>()

const riktning = computed(() => {
  if (props.andring === null) return null
  if (props.andring < 0) return { klass: 'hogre', tecken: '▲' }
  if (props.andring > 0) return { klass: 'lagre', tecken: '▼' }
  return { klass: 'samma', tecken: '=' }
})
</script>

<template>
  <span
    v-if="riktning"
    class="placeringsikon"
    :class="riktning.klass"
    :data-riktning="riktning.klass"
    data-testid="placeringsikon"
    aria-hidden="true"
    >{{ riktning.tecken }}</span
  >
</template>

<style scoped>
.placeringsikon {
  display: inline-block;
  min-width: 1em;
  margin-right: 4px;
  font-weight: 600;
  text-align: center;
}
.hogre {
  color: var(--diverg-hogre);
}
.lagre {
  color: var(--diverg-lagre);
}
.samma {
  color: var(--ink-muted);
}
</style>
