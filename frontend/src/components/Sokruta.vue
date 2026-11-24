<script setup lang="ts">
// Sökrutan i sidhuvudet (#142). Den leder till sidan Sök, där träffarna visas.
import { ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'

const route = useRoute()
const router = useRouter()
const text = ref('')

// På sidan Sök står frågan kvar i rutan.
watch(
  () => (route.path === '/sok' && typeof route.query.q === 'string' ? route.query.q : null),
  (q) => {
    if (q !== null) text.value = q
  },
  { immediate: true },
)

function sok() {
  const q = text.value.trim()
  if (q.length < 2) return
  router.push({ path: '/sok', query: { q } })
}
</script>

<template>
  <form class="sokruta" role="search" aria-label="Sök på plattformen" @submit.prevent="sok">
    <label class="dold" for="sokruta-falt">Sök</label>
    <input
      id="sokruta-falt"
      v-model="text"
      type="search"
      name="q"
      placeholder="Sök i protokoll, ärenden, ledamöter …"
      autocomplete="off"
      minlength="2"
      data-testid="sokruta"
    />
    <button type="submit" data-testid="sokruta-knapp">Sök</button>
  </form>
</template>

<style scoped>
.sokruta {
  display: flex;
  align-items: stretch;
  gap: 4px;
  flex: 1 1 240px;
  max-width: 420px;
  min-width: 0;
}
.dold {
  position: absolute;
  width: 1px;
  height: 1px;
  overflow: hidden;
  clip: rect(0 0 0 0);
  white-space: nowrap;
}
input {
  flex: 1;
  min-width: 0;
  padding: 4px 10px;
  border: 1px solid currentColor;
  border-radius: var(--radius);
  background: rgba(255, 255, 255, 0.12);
  color: inherit;
  font: inherit;
  font-size: 13px;
}
input::placeholder {
  color: inherit;
  opacity: 0.8;
}
button {
  padding: 4px 12px;
  border: 1px solid currentColor;
  border-radius: var(--radius);
  background: none;
  color: inherit;
  font: inherit;
  font-size: 13px;
  cursor: pointer;
}
button:hover {
  background: rgba(255, 255, 255, 0.12);
}
input:focus-visible,
button:focus-visible {
  outline: 2px solid currentColor;
  outline-offset: 2px;
}
</style>
