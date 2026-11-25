<script setup lang="ts">
// Processer ur reglementen och delegationsordningar (#152): de publicerade, i redaktionens ordning. Varje process har en
// egen sida med stegen.
import { inject, onMounted, ref } from 'vue'
import { EjInloggad, hamtaProcesser, type Process } from '../../api'

const utloggad = inject<() => void>('utloggad', () => {})
const processer = ref<Process[] | null>(null)
const fel = ref<string | null>(null)

onMounted(async () => {
  try {
    processer.value = (await hamtaProcesser()).processer
  } catch (e) {
    if (e instanceof EjInloggad) return utloggad()
    fel.value = e instanceof Error ? e.message : String(e)
  }
})
</script>

<template>
  <header class="vyhuvud">
    <p class="tillbaka"><RouterLink to="/politik/styrande-dokument">‹ Styrande dokument</RouterLink></p>
    <h1>Processer</h1>
    <p class="ingress">
      Hur saker ska gå till enligt kommunens reglementen och delegationsordningar, steg för steg: vem som gör något, vad
      som görs, när och var det står. Redaktionen väljer vilka arbetsgångar som beskrivs. Stegen är redaktionens analys,
      granskad och publicerad av en utgivare. Hur det faktiskt går till jämförs inte här.
    </p>
  </header>

  <p v-if="fel" class="fel">Kunde inte hämta uppgifter: {{ fel }}</p>
  <p v-else-if="!processer">Hämtar uppgifter…</p>
  <section v-else class="kort" aria-labelledby="lista-rubrik">
    <h2 id="lista-rubrik">{{ processer.length === 1 ? '1 process' : `${processer.length} processer` }}</h2>
    <p v-if="!processer.length" class="ingress" data-testid="inga">Redaktionen har inte publicerat några processer än.</p>
    <ul class="lista">
      <li v-for="p in processer" :key="p.id" data-testid="processrad">
        <RouterLink :to="`/politik/styrande-dokument/processer/${p.id}`">{{ p.namn }}</RouterLink>
        <span class="analysetikett">Analys</span>
        <span class="not">
          {{ p.steg.length === 1 ? '1 steg' : `${p.steg.length} steg` }} ·
          {{ p.dokument.map((d) => d.titel).join(', ') }}
        </span>
        <span v-if="p.dokument_andrat" class="andrat">Dokumentet har ändrats</span>
      </li>
    </ul>
  </section>
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
.kort h2 {
  margin-bottom: 12px;
}
.lista {
  list-style: none;
  margin: 0;
  padding: 0;
}
.lista li {
  display: flex;
  flex-wrap: wrap;
  align-items: baseline;
  gap: 8px;
  padding: 8px 0;
  border-bottom: 1px solid var(--line);
}
.analysetikett,
.andrat {
  font-size: 12px;
  font-weight: 600;
  color: var(--ink-secondary);
  border: 1px dashed var(--line-strong);
  border-radius: var(--radius);
  padding: 0 6px;
}
.andrat {
  border-style: solid;
}
.not {
  font-size: 13px;
  color: var(--ink-muted);
}
.fel {
  color: var(--status-critical);
}
</style>
