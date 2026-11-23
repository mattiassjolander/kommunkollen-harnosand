<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'

/*
 * Byter mellan ljust och mörkt läge. Utan eget val följer sidan systemets inställning.
 * Valet sparas i webbläsaren och sätts som data-theme på <html> (se tokens.css).
 * index.html sätter samma attribut innan sidan ritas, så att den inte blinkar till.
 */
type Tema = 'ljust' | 'morkt'
const NYCKEL = 'kommunkollen-tema'

const systemMorkt = window.matchMedia('(prefers-color-scheme: dark)')
const sparat = ref<Tema | null>(lasSparat())
const systemetArMorkt = ref(systemMorkt.matches)

const tema = computed<Tema>(() => sparat.value ?? (systemetArMorkt.value ? 'morkt' : 'ljust'))

function lasSparat(): Tema | null {
  try {
    const v = localStorage.getItem(NYCKEL)
    return v === 'ljust' || v === 'morkt' ? v : null
  } catch {
    return null
  }
}

function satt(nytt: Tema) {
  sparat.value = nytt
  document.documentElement.dataset.theme = nytt === 'morkt' ? 'dark' : 'light'
  try {
    localStorage.setItem(NYCKEL, nytt)
  } catch {
    // Valet gäller då bara tills sidan laddas om.
  }
}

function vaxla() {
  satt(tema.value === 'morkt' ? 'ljust' : 'morkt')
}

function systemetAndrades(e: MediaQueryListEvent) {
  systemetArMorkt.value = e.matches
}

onMounted(() => systemMorkt.addEventListener('change', systemetAndrades))
onBeforeUnmount(() => systemMorkt.removeEventListener('change', systemetAndrades))
</script>

<template>
  <button
    type="button"
    class="temaknapp"
    data-testid="temavaljare"
    :data-tema="tema"
    :aria-label="tema === 'morkt' ? 'Byt till ljust läge' : 'Byt till mörkt läge'"
    @click="vaxla"
  >
    <span aria-hidden="true">{{ tema === 'morkt' ? '☀' : '☾' }}</span>
    {{ tema === 'morkt' ? 'Ljust läge' : 'Mörkt läge' }}
  </button>
</template>

<style scoped>
.temaknapp {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 4px 12px;
  border: 1px solid currentColor;
  border-radius: var(--radius);
  background: none;
  color: inherit;
  font: inherit;
  font-size: 13px;
  cursor: pointer;
  white-space: nowrap;
}
.temaknapp:hover {
  background: rgba(255, 255, 255, 0.12);
}
.temaknapp:focus-visible {
  outline: 2px solid currentColor;
  outline-offset: 2px;
}
</style>
