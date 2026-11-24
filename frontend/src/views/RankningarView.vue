<script setup lang="ts">
// Rankningar (#66): en ruta per rankning med Härnösands senaste placering, förändringen mot året innan,
// avsändare och år. Plattformen värderar inte placeringarna (kravspec avsnitt 18).
import { inject, onMounted, ref } from 'vue'
import { EjInloggad, hamtaRankningar, type Rankningsinfo } from '../api'
import { rankningsandring, tal2 } from '../rankning'

const rankningar = ref<Rankningsinfo[]>([])
const laddar = ref(true)
const fel = ref<string | null>(null)
const utloggad = inject<() => void>('utloggad', () => {})

onMounted(async () => {
  try {
    rankningar.value = await hamtaRankningar()
  } catch (e) {
    if (e instanceof EjInloggad) return utloggad()
    fel.value = e instanceof Error ? e.message : String(e)
  } finally {
    laddar.value = false
  }
})
</script>

<template>
  <header class="vyhuvud">
    <h1>Rankningar</h1>
    <p class="ingress">
      Externa aktörer rankar Sveriges kommuner varje år, var och en efter en egen metod. Här visas Härnösands placering
      i några av dem, med grannkommunerna och delmåtten. Varje rankning anger vem som står bakom den. Kommunkollen gör
      inga egna bedömningar av vad en placering betyder.
    </p>
  </header>

  <p v-if="laddar">Hämtar uppgifter…</p>
  <p v-else-if="fel" class="fel">Kunde inte hämta uppgifter: {{ fel }}</p>
  <p v-else-if="!rankningar.length">Inga rankningar har hämtats än.</p>

  <div v-else class="rutnat">
    <RouterLink
      v-for="r in rankningar"
      :key="r.id"
      :to="`/rankningar/${r.id}`"
      class="kort rankningskort"
      data-testid="rankningskort"
    >
      <span class="titel">{{ r.titel }} ›</span>
      <span class="avsandare">{{ r.avsandare }} · {{ r.avsandartyp }}</span>
      <template v-if="r.senaste">
        <span class="placering" data-testid="placering">
          Plats {{ r.senaste.placering }}<span v-if="r.senaste.antal" class="av"> av {{ r.senaste.antal }}</span>
        </span>
        <span class="ar">Härnösand {{ r.senaste.ar }}</span>
        <span v-if="r.senaste.poang !== null" class="detalj">
          {{ tal2(r.senaste.poang) }}<template v-if="r.senaste.max_poang !== null"> av {{ tal2(r.senaste.max_poang) }}</template>
          poäng
        </span>
        <span v-if="r.senaste.foregaende" class="detalj" data-testid="forandring">
          {{ r.senaste.foregaende.ar }}: plats {{ r.senaste.foregaende.placering }} ·
          {{ rankningsandring(r.senaste.andring) }}
        </span>
      </template>
      <span v-else class="detalj">Ingen placering för Härnösand än.</span>
      <span class="kalla">Källa: {{ r.avsandare }}</span>
    </RouterLink>
  </div>
</template>

<style scoped>
.vyhuvud {
  margin-bottom: 24px;
}
.vyhuvud h1 {
  color: var(--accent);
}
.ingress {
  color: var(--ink-secondary);
  margin: 0;
  max-width: 70ch;
}
.rutnat {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(300px, 1fr));
  gap: 16px;
}
.kort {
  background: var(--surface);
  border: 1px solid var(--line);
  border-radius: var(--radius);
  padding: 20px 24px;
}
.rankningskort {
  display: flex;
  flex-direction: column;
  gap: 4px;
  text-decoration: none;
  color: var(--ink);
}
.rankningskort:hover {
  border-color: var(--accent);
  background: var(--accent-wash);
}
.rankningskort:focus-visible {
  outline: 2px solid var(--accent);
  outline-offset: 2px;
}
.titel {
  font-weight: 600;
  color: var(--accent);
}
.avsandare {
  font-size: 13px;
  color: var(--ink-secondary);
  margin-bottom: 8px;
}
.placering {
  font-size: 28px;
  font-weight: 600;
}
.av {
  font-size: 15px;
  font-weight: 400;
  color: var(--ink-secondary);
}
.ar,
.detalj {
  font-size: 13px;
  color: var(--ink-secondary);
}
.kalla {
  font-size: 12px;
  color: var(--ink-muted);
  margin-top: 8px;
}
.fel {
  color: var(--status-critical);
}
</style>
