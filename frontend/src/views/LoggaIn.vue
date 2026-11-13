<script setup lang="ts">
import { computed } from 'vue'
import { testinloggning, type Inloggningsmetod } from '../api'

const props = defineProps<{ metod: Inloggningsmetod; kanAvbryta: boolean }>()
const emit = defineEmits<{ inloggad: []; avbryt: [] }>()

const testroller = computed(() =>
  // Med öppen läsning finns inget skäl att logga in som läsare.
  [
    { roll: 'lasare', namn: 'läsare' },
    { roll: 'redaktor', namn: 'redaktör' },
    { roll: 'utgivare', namn: 'utgivare' },
  ].filter((r) => !(props.metod.anonym_lasning && r.roll === 'lasare')),
)
const felkod = new URLSearchParams(window.location.search).get('fel')

const felmeddelande = computed(() => {
  if (felkod === 'ej-behorig')
    return 'Det Google-kontot har inte åtkomst till Kommunkollen. Kontakta den som administrerar plattformen om du behöver åtkomst.'
  if (felkod === 'inloggning-misslyckades') return 'Inloggningen misslyckades. Försök igen.'
  return null
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
      <p v-if="metod.anonym_lasning" class="text">
        Allt innehåll går att läsa utan inloggning. Inloggning behövs bara för redaktörer och utgivare.
      </p>
      <p v-else class="text">Plattformen är under uppbyggnad och kräver inloggning.</p>

      <p v-if="felmeddelande" class="fel" role="alert" data-testid="inloggningsfel">{{ felmeddelande }}</p>

      <a v-if="metod.google" class="knapp primar" href="/api/auth/google/start">Logga in med Google</a>
      <p v-else-if="!metod.test" class="text">Ingen inloggningsmetod är konfigurerad.</p>

      <div v-if="metod.test" class="test">
        <p class="testetikett">Testmiljö</p>
        <button v-for="r in testroller" :key="r.roll" class="knapp" type="button" @click="loggaInSom(r.roll)">
          Logga in som {{ r.namn }} (test)
        </button>
      </div>

      <button v-if="kanAvbryta" class="knapp" type="button" @click="emit('avbryt')">
        Fortsätt utan att logga in
      </button>
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
