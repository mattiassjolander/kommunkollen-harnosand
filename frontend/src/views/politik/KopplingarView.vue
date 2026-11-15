<script setup lang="ts">
// Kön med kopplingsförslag (ADR-0002, ADR-0003). En redaktör bekräftar eller avvisar varje förslag.
import { computed, inject, onMounted, ref, type Ref } from 'vue'
import {
  avvisaKoppling,
  bekraftaKoppling,
  EjInloggad,
  hamtaKopplingar,
  type Behandlingsref,
  type Jag,
  type Koppling,
} from '../../api'
import { sammantradesdatum } from '../../format'
import Kopplingsmarkering from '../../components/Kopplingsmarkering.vue'
import PolitikFlikar from '../../components/PolitikFlikar.vue'

const utloggad = inject<() => void>('utloggad', () => {})
const jag = inject<Ref<Jag | null>>('jag', ref(null))
const arRedaktor = computed(() => jag.value?.roller.includes('redaktor') ?? false)

const forslag = ref<Koppling[]>([])
const beslutade = ref<Koppling[]>([])
const laddar = ref(true)
const fel = ref<string | null>(null)
const arbetar = ref<number | null>(null)

onMounted(async () => {
  if (!arRedaktor.value) {
    laddar.value = false
    return
  }
  try {
    forslag.value = await hamtaKopplingar('forslag')
  } catch (e) {
    if (e instanceof EjInloggad) return utloggad()
    fel.value = e instanceof Error ? e.message : String(e)
  } finally {
    laddar.value = false
  }
})

async function besluta(k: Koppling, bekrafta: boolean) {
  arbetar.value = k.id
  fel.value = null
  try {
    const ny = await (bekrafta ? bekraftaKoppling(k.id) : avvisaKoppling(k.id))
    forslag.value = forslag.value.filter((f) => f.id !== k.id)
    beslutade.value = [ny, ...beslutade.value]
  } catch (e) {
    if (e instanceof EjInloggad) return utloggad()
    fel.value = e instanceof Error ? e.message : String(e)
  } finally {
    arbetar.value = null
  }
}

const lank = (b: Behandlingsref) => `/politik/sammantraden/${b.sammantrade.id}/paragraf/${b.paragraf}`
</script>

<template>
  <header class="vyhuvud">
    <h1>Politik och beslut</h1>
    <p class="ingress">
      Förslag på kopplingar mellan behandlingar som plattformen inte kunnat göra säkert, till exempel när ett
      beslutsunderlag hänvisar till ett senare organ eller inte anger organet. En bekräftad koppling för ihop
      behandlingarna till ett ärende.
    </p>
  </header>
  <PolitikFlikar />

  <p v-if="!arRedaktor" class="saknas">Kön visas bara för redaktörer.</p>
  <p v-else-if="laddar">Hämtar förslag…</p>
  <template v-else>
    <p v-if="fel" class="fel" role="alert">{{ fel }}</p>
    <p class="antal" data-testid="antal-forslag">{{ forslag.length }} förslag att granska</p>

    <ul class="ko" data-testid="kopplingsko">
      <li v-for="k in forslag" :key="k.id" class="kort" data-testid="kopplingsforslag">
        <div class="par">
          <div v-for="(b, i) in [k.fran, k.till]" :key="i" class="sida">
            <p class="anteckning">
              {{ i === 0 ? 'Tidigare' : 'Senare' }} · {{ b.sammantrade.organ.namn }},
              {{ sammantradesdatum(b.sammantrade.datum) }}
            </p>
            <RouterLink :to="lank(b)">§ {{ b.paragraf }} {{ b.rubrik }}</RouterLink>
          </div>
        </div>
        <p class="grund"><Kopplingsmarkering :koppling="k" /></p>
        <div class="knappar">
          <button
            type="button"
            class="knapp primar"
            :disabled="arbetar === k.id"
            data-testid="bekrafta"
            @click="besluta(k, true)"
          >
            Bekräfta koppling
          </button>
          <button type="button" class="knapp" :disabled="arbetar === k.id" data-testid="avvisa" @click="besluta(k, false)">
            Avvisa
          </button>
        </div>
      </li>
    </ul>

    <section v-if="beslutade.length" aria-labelledby="besl-rubrik">
      <h2 id="besl-rubrik">Beslutade nu</h2>
      <ul class="lista" data-testid="beslutade">
        <li v-for="k in beslutade" :key="k.id">
          <RouterLink :to="lank(k.till)">{{ k.till.sammantrade.organ.namn }} § {{ k.till.paragraf }}</RouterLink>
          ← {{ k.fran.sammantrade.organ.namn }} § {{ k.fran.paragraf }}
          <span class="anteckning"><Kopplingsmarkering :koppling="k" /></span>
        </li>
      </ul>
    </section>
  </template>
</template>

<style scoped>
.vyhuvud {
  margin-bottom: 24px;
}
.ingress {
  color: var(--ink-secondary);
  margin: 0;
  max-width: 70ch;
}
.antal {
  font-size: 13px;
  color: var(--ink-secondary);
}
.ko {
  list-style: none;
  margin: 0 0 24px;
  padding: 0;
  display: grid;
  gap: 16px;
}
.kort {
  background: var(--surface);
  border: 1px solid var(--line);
  border-radius: var(--radius);
  padding: 20px 24px;
}
.par {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 24px;
}
@media (max-width: 800px) {
  .par {
    grid-template-columns: 1fr;
  }
}
.sida a {
  color: var(--accent);
}
.anteckning {
  font-size: 12px;
  color: var(--ink-muted);
  margin: 0 0 2px;
}
.grund {
  margin: 12px 0;
}
.knappar {
  display: flex;
  gap: 8px;
}
.knapp {
  font: inherit;
  font-size: 13px;
  padding: 6px 14px;
  border-radius: var(--radius);
  border: 1px solid var(--line);
  background: var(--surface);
  color: var(--ink);
  cursor: pointer;
}
.knapp.primar {
  background: var(--accent);
  border-color: var(--accent);
  color: var(--surface);
}
.knapp:disabled {
  opacity: 0.6;
  cursor: default;
}
.lista {
  list-style: none;
  margin: 0;
  padding: 0;
  font-size: 13px;
}
.lista li {
  padding: 6px 0;
  border-bottom: 1px solid var(--line);
}
.lista .anteckning {
  display: block;
}
.saknas {
  color: var(--ink-muted);
  font-style: italic;
}
.fel {
  color: var(--status-critical);
}
</style>
