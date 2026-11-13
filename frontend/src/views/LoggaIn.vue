<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { hamtaInloggningsmetod, testinloggning, type Inloggningsmetod } from '../api'

const emit = defineEmits<{ inloggad: [] }>()

const metod = ref<Inloggningsmetod | null>(null)
const felkod = new URLSearchParams(window.location.search).get('fel')

const felmeddelande = computed(() => {
  if (felkod === 'ej-behorig')
    return 'Det Google-kontot har inte åtkomst till Kommunkollen. Kontakta den som administrerar plattformen om du behöver åtkomst.'
  if (felkod === 'inloggning-misslyckades') return 'Inloggningen misslyckades. Försök igen.'
  return null
})

onMounted(async () => {
  metod.value = await hamtaInloggningsmetod()
})

async function loggaInSom(roll: string) {
  await testinloggning(roll)
  history.replaceState(null, '', window.location.pathname)
  emit('inloggad')
}
</script>

<template>
  <div class="sida">
    <section class="ruta">
      <div class="ordmarke">
        <span class="namn">Kommunkollen</span>
        <span class="ort">Härnösand</span>
      </div>
      <p class="text">Plattformen är under uppbyggnad och kräver inloggning.</p>

      <p v-if="felmeddelande" class="fel" role="alert" data-testid="inloggningsfel">{{ felmeddelande }}</p>

      <a v-if="metod?.google" class="knapp primar" href="/api/auth/google/start">Logga in med Google</a>
      <p v-else-if="metod && !metod.test" class="text">Ingen inloggningsmetod är konfigurerad.</p>

      <div v-if="metod?.test" class="test">
        <p class="testetikett">Testmiljö</p>
        <button class="knapp" type="button" @click="loggaInSom('lasare')">Logga in som läsare (test)</button>
        <button class="knapp" type="button" @click="loggaInSom('redaktor')">Logga in som redaktör (test)</button>
        <button class="knapp" type="button" @click="loggaInSom('utgivare')">Logga in som utgivare (test)</button>
      </div>
    </section>
  </div>
</template>

<style scoped>
.sida {
  min-height: 100vh;
  display: grid;
  place-items: center;
  padding: 16px;
}
.ruta {
  background: var(--surface);
  border: 1px solid var(--line);
  border-radius: var(--radius);
  padding: 32px;
  width: 100%;
  max-width: 400px;
  display: flex;
  flex-direction: column;
  gap: 12px;
}
.ordmarke {
  display: flex;
  flex-direction: column;
  margin-bottom: 8px;
}
.namn {
  font-weight: 600;
  font-size: 24px;
}
.ort {
  color: var(--ink-secondary);
}
.text {
  color: var(--ink-secondary);
  margin: 0;
}
.fel {
  margin: 0;
  color: var(--ink);
  border-left: 3px solid var(--status-critical);
  padding-left: 12px;
}
.knapp {
  display: block;
  text-align: center;
  padding: 10px 16px;
  border-radius: var(--radius);
  border: 1px solid var(--line-strong);
  background: var(--surface-raised);
  color: var(--ink);
  font: inherit;
  text-decoration: none;
  cursor: pointer;
}
.knapp:hover {
  background: var(--accent-wash);
}
.primar {
  background: var(--accent);
  border-color: var(--accent);
  color: var(--surface-raised);
  font-weight: 600;
}
.primar:hover {
  background: var(--accent);
  opacity: 0.9;
}
.test {
  display: flex;
  flex-direction: column;
  gap: 8px;
  border-top: 1px solid var(--line);
  padding-top: 12px;
}
.testetikett {
  margin: 0;
  font-size: 12px;
  color: var(--ink-muted);
  text-transform: uppercase;
  letter-spacing: 0.04em;
}
</style>
