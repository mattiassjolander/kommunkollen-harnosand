<script setup lang="ts">
import type { Tema } from '../hogtider'

/* Den korta raden i sidhuvudet under en högtid (docs/design.md, Högtidsteman). */
defineProps<{ tema: Tema }>()
</script>

<template>
  <p class="rad" data-testid="hogtidsrad" :data-tema="tema.namn">
    <span
      v-if="tema.tooltip"
      class="med-kalla"
      tabindex="0"
      aria-describedby="hogtidsrad-kalla"
      data-testid="hogtidsrad-text"
    >
      {{ tema.text }}
      <span id="hogtidsrad-kalla" role="tooltip" class="kalla" data-testid="hogtidsrad-kalla">{{ tema.tooltip }}</span>
    </span>
    <span v-else data-testid="hogtidsrad-text">{{ tema.text }}</span>
    <template v-if="tema.lank">
      –
      <a :href="tema.lank.href" target="_blank" rel="noopener">{{ tema.lank.text }}</a>
    </template>
  </p>
</template>

<style scoped>
.rad {
  margin: 0;
  font-size: 13px;
  font-weight: 600;
  color: var(--sidhuvud-ink);
}
a {
  color: var(--sidhuvud-ink);
}
.med-kalla {
  position: relative;
  text-decoration: underline dotted;
  text-underline-offset: 3px;
  cursor: help;
}
.med-kalla:focus-visible {
  outline: 2px solid var(--sidhuvud-ink);
  outline-offset: 2px;
}
/* Tooltip med källan. Sidhuvudets färger byts, så att texten håller kontrasten i båda lägena. */
.kalla {
  display: none;
  position: absolute;
  top: calc(100% + 8px);
  left: 0;
  z-index: 10;
  width: max-content;
  max-width: min(360px, 80vw);
  padding: 8px 12px;
  border-radius: var(--radius);
  background: var(--sidhuvud-ink);
  color: var(--sidhuvud);
  font-weight: 400;
  font-size: 12px;
  box-shadow: var(--shadow-float);
}
.med-kalla:hover .kalla,
.med-kalla:focus .kalla {
  display: block;
}
</style>
