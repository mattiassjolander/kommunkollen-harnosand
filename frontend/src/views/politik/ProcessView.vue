<script setup lang="ts">
// Processidan (#152): stegen i ordning med vem, vad, när, citat och källa, och publicerade motstridigheter vid stegen
// de rör. Hela processen är redaktionens analys och märks Analys.
import { inject, ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import { EjInloggad, Saknas, hamtaProcess, type Process } from '../../api'
import { datum } from '../../format'
import { dokumenttitel } from '../../navigering'
import Processkort from '../../components/Processkort.vue'

const route = useRoute()
const utloggad = inject<() => void>('utloggad', () => {})
const p = ref<Process | null>(null)
const laddar = ref(true)
const saknas = ref(false)
const fel = ref<string | null>(null)

watch(
  () => route.params.id,
  async (id) => {
    laddar.value = true
    saknas.value = false
    fel.value = null
    try {
      p.value = await hamtaProcess(Number(id))
      document.title = dokumenttitel(route.path, p.value.namn)
    } catch (e) {
      if (e instanceof EjInloggad) return utloggad()
      if (e instanceof Saknas) saknas.value = true
      else fel.value = e instanceof Error ? e.message : String(e)
    } finally {
      laddar.value = false
    }
  },
  { immediate: true },
)
</script>

<template>
  <p v-if="laddar">Hämtar uppgifter…</p>
  <p v-else-if="saknas">Processen finns inte.</p>
  <p v-else-if="fel" class="fel">Kunde inte hämta uppgifter: {{ fel }}</p>
  <template v-else-if="p">
    <header class="vyhuvud">
      <p class="tillbaka"><RouterLink to="/politik/styrande-dokument/processer">‹ Processer</RouterLink></p>
      <h1>{{ p.namn }}</h1>
      <p class="ingress">
        Stegen som de står i kommunens reglementen och delegationsordningar, i ordning. Redaktionens analys, publicerad
        {{ datum(p.publicerad) }}. Varje steg har ett ordagrant citat med länk till sidan i dokumentet.
      </p>
    </header>
    <section class="kort" aria-label="Steg">
      <Processkort :p="p" diagram />
    </section>
  </template>
</template>

<style scoped>
.vyhuvud {
  margin-bottom: 16px;
}
.tillbaka {
  margin: 0 0 8px;
  font-size: 13px;
}
.ingress {
  color: var(--ink-secondary);
  max-width: 70ch;
}
.kort {
  background: var(--surface);
  border: 1px solid var(--line);
  border-radius: var(--radius);
  padding: 24px;
  margin-bottom: 24px;
}
.fel {
  color: var(--status-critical);
}
</style>
