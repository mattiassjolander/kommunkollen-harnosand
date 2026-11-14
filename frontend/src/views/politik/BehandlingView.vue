<script setup lang="ts">
import { computed, inject, ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import { EjInloggad, hamtaBehandling, Saknas, type Behandling } from '../../api'
import { namnOchParti, parti, sammantradesdatum } from '../../format'
import Protokollkalla from '../../components/Protokollkalla.vue'
import Tolkningsmarkering from '../../components/Tolkningsmarkering.vue'

const route = useRoute()
const utloggad = inject<() => void>('utloggad', () => {})

const b = ref<Behandling | null>(null)
const laddar = ref(true)
const fel = ref<string | null>(null)

async function ladda() {
  laddar.value = true
  fel.value = null
  try {
    b.value = await hamtaBehandling(String(route.params.id), String(route.params.paragraf))
  } catch (e) {
    if (e instanceof EjInloggad) return utloggad()
    fel.value = e instanceof Saknas ? 'Paragrafen finns inte i sammanträdet.' : e instanceof Error ? e.message : String(e)
  } finally {
    laddar.value = false
  }
}
watch(() => [route.params.id, route.params.paragraf], ladda, { immediate: true })

const sammantradeslank = computed(() => `/politik/sammantraden/${route.params.id}`)
const lank = (p: number) => `${sammantradeslank.value}/paragraf/${p}`
</script>

<template>
  <nav class="brodsmulor" aria-label="Brödsmulor">
    <RouterLink to="/politik">Politik och beslut</RouterLink>
    <span aria-hidden="true">›</span>
    <RouterLink :to="sammantradeslank">
      {{ b ? `${b.sammantrade.organ.namn} ${b.sammantrade.datum ?? ''}` : 'Sammanträde' }}
    </RouterLink>
    <span aria-hidden="true">›</span>
    <span>§ {{ route.params.paragraf }}</span>
  </nav>

  <p v-if="laddar">Hämtar uppgifter…</p>
  <p v-else-if="fel" class="fel">{{ fel }}</p>

  <template v-else-if="b">
    <header class="vyhuvud">
      <p class="overrubrik">
        § {{ b.paragraf }} · {{ b.sammantrade.organ.namn }},
        <span class="forsta-versal">{{ sammantradesdatum(b.sammantrade.datum) }}</span>
      </p>
      <h1>{{ b.rubrik || 'Rubrik saknas' }}</h1>
      <p v-if="b.diarienummer.length" class="ingress" data-testid="diarienummer">
        Diarienummer {{ b.diarienummer.join(', ') }}
      </p>
      <p class="markering"><Tolkningsmarkering /></p>
      <Protokollkalla :protokoll="b.sammantrade.protokoll" :paragraf="b.paragraf" />
    </header>

    <section class="kort" aria-labelledby="beslut-rubrik">
      <h2 id="beslut-rubrik">Beslut</h2>
      <p v-if="b.beslut" class="beslut" data-testid="beslut">{{ b.beslut }}</p>
      <p v-else class="saknas" data-testid="beslut">Protokollet anger inget beslut för paragrafen.</p>
    </section>

    <section class="kort" aria-labelledby="besl-rubrik" data-testid="beslutande">
      <h2 id="besl-rubrik">Beslutande vid paragrafen <span class="antal">({{ b.beslutande.length }})</span></h2>
      <p class="ingress">
        Räknat ur närvarolistan, med hänsyn till jäv och ersättare som tjänstgjorde bara vid vissa paragrafer.
      </p>
      <ul class="personer">
        <li v-for="p in b.beslutande" :key="p.namn" data-testid="person">
          {{ p.namn }} <span :class="{ saknas: p.parti === null }">({{ parti(p.parti) }})</span>
          <span v-if="p.tjanstgor_for" class="anteckning">
            tjänstgör för {{ namnOchParti(p.tjanstgor_for.namn, p.tjanstgor_for.parti) }}
          </span>
        </li>
      </ul>
      <template v-if="b.jav.length">
        <h3>Jäv</h3>
        <ul class="personer" data-testid="jav">
          <li v-for="p in b.jav" :key="p.namn">{{ namnOchParti(p.namn, p.parti) }}</li>
        </ul>
      </template>
    </section>

    <nav class="blader" aria-label="Paragrafer">
      <RouterLink v-if="b.foregaende !== null" :to="lank(b.foregaende)" data-testid="foregaende">
        ‹ § {{ b.foregaende }}
      </RouterLink>
      <span v-else />
      <RouterLink v-if="b.nasta !== null" :to="lank(b.nasta)" data-testid="nasta">§ {{ b.nasta }} ›</RouterLink>
    </nav>
  </template>
</template>

<style scoped>
.brodsmulor {
  display: flex;
  gap: 8px;
  font-size: 13px;
  color: var(--ink-muted);
  margin-bottom: 12px;
}
.brodsmulor a {
  color: var(--accent);
}
.vyhuvud {
  margin-bottom: 24px;
}
.overrubrik {
  font-size: 13px;
  color: var(--ink-secondary);
  margin: 0 0 4px;
}
.forsta-versal {
  display: inline-block;
}
.ingress {
  color: var(--ink-secondary);
  margin: 0;
  max-width: 70ch;
}
.markering {
  margin: 12px 0 0;
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
.kort h3 {
  font-size: 14px;
  margin: 20px 0 8px;
}
.antal {
  color: var(--ink-muted);
  font-weight: 400;
}
.beslut {
  white-space: pre-line;
  max-width: 80ch;
  margin: 0;
}
.personer {
  columns: 3 240px;
  margin: 12px 0 0;
  padding: 0;
  list-style: none;
  font-size: 13px;
}
.personer li {
  break-inside: avoid;
  padding: 2px 0;
}
.anteckning {
  display: block;
  font-size: 12px;
  color: var(--ink-muted);
}
.saknas {
  color: var(--ink-muted);
  font-style: italic;
}
.blader {
  display: flex;
  justify-content: space-between;
  font-size: 13px;
}
.blader a {
  color: var(--accent);
}
.fel {
  color: var(--status-critical);
}
</style>
