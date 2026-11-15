<script setup lang="ts">
import { computed, inject, onMounted, ref } from 'vue'
import {
  EjInloggad,
  hamtaEkonomi,
  hamtaStatus,
  type GlobalStatus,
  type Nyckeltal,
  type Nyckeltalsgrupp,
} from '../api'
import { datumTid } from '../format'
import Statkort from '../components/Statkort.vue'
import StatusMarkering from '../components/StatusMarkering.vue'

// Urvalet på översikten: de nyckeltal i kravspec 3.1 som säger mest om läget, ett per område.
// Alla finns också i ekonomivyn med hela tidsserien.
const URVAL = [
  'scb:ResultKnN:120', // Årets resultat
  'kolada:N03102', // Resultat som andel av skatt och statsbidrag
  'scb:ResultKnN:040', // Skatteintäkter
  'kolada:N03100', // Nettokostnadsandel
  'kolada:N03132', // Nettoinvesteringar
  'kolada:N03046', // Långfristiga skulder
  'scb:BalansKnN:065', // Likvida medel
  'kolada:N03106', // Soliditet
]

const GENVAGAR = [
  {
    till: '/ekonomi',
    namn: 'Ekonomi',
    text: 'Alla ekonomiska nyckeltal över tid, med jämförelse mellan år, mandatperioder och export.',
  },
  {
    till: '/floden',
    namn: 'Ekonomiska flöden – Sankey',
    text: 'Hur intäkterna fördelas på verksamhetsområden, och vad varje område kostar.',
  },
  {
    till: '/datakallor',
    namn: 'Datakällor',
    text: 'Var uppgifterna kommer ifrån, när de senast hämtades och om något gick fel.',
  },
]

const grupper = ref<Nyckeltalsgrupp[]>([])
const status = ref<GlobalStatus | null>(null)
const laddar = ref(true)
const fel = ref<string | null>(null)
const utloggad = inject<() => void>('utloggad', () => {})

onMounted(async () => {
  try {
    const [ekonomi, s] = await Promise.all([hamtaEkonomi(), hamtaStatus()])
    grupper.value = ekonomi.grupper
    status.value = s
  } catch (e) {
    if (e instanceof EjInloggad) return utloggad()
    fel.value = e instanceof Error ? e.message : String(e)
  } finally {
    laddar.value = false
  }
})

const kort = computed(() =>
  URVAL.flatMap((id) => {
    const grupp = grupper.value.find((g) => g.nyckeltal.some((n) => n.id === id))
    const nyckeltal = grupp?.nyckeltal.find((n) => n.id === id) as Nyckeltal | undefined
    return grupp && nyckeltal ? [{ nyckeltal, lank: `/ekonomi#${grupp.id}` }] : []
  }),
)
const medFel = computed(() => (status.value ? status.value.kallor_kontrollerade - status.value.kallor_utan_fel : 0))
</script>

<template>
  <figure class="platsbild">
    <img src="/platsvarumarke/smitingen.jpg" alt="Strandkant vid Smitingen" />
    <figcaption>Foto: Härnösands platsvarumärke</figcaption>
  </figure>
  <header class="vyhuvud">
    <h1>Översikt</h1>
    <p class="ingress">
      En snabb bild av Härnösands kommuns ekonomi. Senaste värdet för de viktigaste nyckeltalen och förändringen mot
      året före, i löpande priser.
    </p>
  </header>

  <p v-if="laddar">Hämtar uppgifter…</p>
  <p v-else-if="fel" class="fel">Kunde inte hämta uppgifter: {{ fel }}</p>

  <template v-else>
    <section aria-labelledby="nyckeltal-rubrik" class="sektion">
      <h2 id="nyckeltal-rubrik">Nyckeltal</h2>
      <div class="statrutnat">
        <Statkort v-for="k in kort" :key="k.nyckeltal.id" :nyckeltal="k.nyckeltal" :lank="k.lank" />
      </div>
    </section>

    <div class="nedre">
      <section v-if="status" class="kort statuspanel" aria-labelledby="status-rubrik" data-testid="statuspanel">
        <h2 id="status-rubrik">Datainsamling</h2>
        <template v-if="status.senaste_korning">
          <StatusMarkering
            :status="status.fullstandigt_uppdaterad ? 'lyckad' : 'delvis_fel'"
            :text="status.fullstandigt_uppdaterad ? 'Fullständigt uppdaterad' : 'Delvis inaktuell'"
          />
          <dl>
            <dt>Senaste insamling</dt>
            <dd data-testid="senaste-insamling">{{ datumTid(status.senaste_korning.avslutad) }}</dd>
            <dt>Senast lyckad</dt>
            <dd>
              {{ status.senaste_lyckade_korning ? datumTid(status.senaste_lyckade_korning.avslutad) : 'Ingen än' }}
            </dd>
            <dt>Nästa insamling</dt>
            <dd data-testid="nasta-insamling">
              {{ status.nasta_korning ? datumTid(status.nasta_korning) : 'Schemat är avstängt' }}
            </dd>
            <dt>Datakällor</dt>
            <dd data-testid="kallstatus">
              {{ status.kallor_utan_fel }} av {{ status.kallor_kontrollerade }} kontrollerade utan fel{{
                medFel ? `, ${medFel} med fel` : ''
              }}
            </dd>
          </dl>
        </template>
        <template v-else>
          <StatusMarkering status="aldrig" text="Ingen insamling har körts än" />
          <dl v-if="status.nasta_korning">
            <dt>Nästa insamling</dt>
            <dd data-testid="nasta-insamling">{{ datumTid(status.nasta_korning) }}</dd>
          </dl>
        </template>
        <RouterLink to="/datakallor" class="lank">Status per datakälla</RouterLink>
      </section>

      <nav class="genvagar" aria-label="Genvägar" data-testid="genvagar">
        <RouterLink v-for="g in GENVAGAR" :key="g.till" :to="g.till" class="kort genvag">
          <span class="genvagsnamn">{{ g.namn }} ›</span>
          <span class="genvagstext">{{ g.text }}</span>
        </RouterLink>
      </nav>
    </div>
  </template>
</template>

<style scoped>
/* Bild ur platsvarumärket, kant i kant med innehållsytan (design.md, Platsvarumärket). */
.platsbild {
  position: relative;
  margin: -32px -48px 24px;
  height: 200px;
  overflow: hidden;
}
.platsbild img {
  width: 100%;
  height: 100%;
  object-fit: cover;
  display: block;
}
.platsbild figcaption {
  position: absolute;
  right: 12px;
  bottom: 6px;
  color: #ffffff;
  font-size: 12px;
  text-shadow: 0 1px 2px rgba(0, 0, 0, 0.7);
}
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
.sektion {
  margin-bottom: 32px;
}
.sektion h2,
.statuspanel h2 {
  margin-bottom: 16px;
}
.statrutnat {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(260px, 1fr));
  gap: 16px;
}
.nedre {
  display: grid;
  grid-template-columns: minmax(0, 1fr) minmax(0, 2fr);
  gap: 16px;
  align-items: start;
}
@media (max-width: 1300px) {
  .nedre {
    grid-template-columns: 1fr;
  }
}
.kort {
  background: var(--surface);
  border: 1px solid var(--line);
  border-radius: var(--radius);
  padding: 20px 24px;
}
.statuspanel dl {
  display: grid;
  grid-template-columns: auto 1fr;
  gap: 6px 16px;
  margin: 16px 0;
  font-size: 13px;
}
.statuspanel dt {
  color: var(--ink-muted);
}
.statuspanel dd {
  margin: 0;
}
.lank {
  font-size: 13px;
}
.genvagar {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 16px;
}
@media (max-width: 800px) {
  .genvagar {
    grid-template-columns: 1fr;
  }
}
.genvag {
  display: flex;
  flex-direction: column;
  gap: 6px;
  text-decoration: none;
  color: var(--ink);
}
.genvag:hover {
  border-color: var(--accent);
  background: var(--accent-wash);
}
.genvag:focus-visible {
  outline: 2px solid var(--accent);
  outline-offset: 2px;
}
.genvagsnamn {
  font-weight: 600;
  color: var(--accent);
}
.genvagstext {
  font-size: 13px;
  color: var(--ink-secondary);
}
.fel {
  color: var(--status-critical);
}
</style>
