<script setup lang="ts">
// Ärendespårning (vy 8): ärendets väg genom organen i tidsordning, med kopplingarna mellan
// behandlingarna (ADR-0003).
import { computed, inject, ref, watch, type Ref } from 'vue'
import { useRoute } from 'vue-router'
import { EjInloggad, hamtaArende, Saknas, type Arende, type Jag, type Koppling } from '../../api'
import { sammantradesdatum } from '../../format'
import Kallelsemarkering from '../../components/Kallelsemarkering.vue'
import Kopplingsmarkering from '../../components/Kopplingsmarkering.vue'
import Tolkningsmarkering from '../../components/Tolkningsmarkering.vue'

const route = useRoute()
const utloggad = inject<() => void>('utloggad', () => {})
const jag = inject<Ref<Jag | null>>('jag', ref(null))
const arRedaktor = computed(() => jag.value?.roller.includes('redaktor') ?? false)

/** Redaktörens väg till beslutet om en koppling, för att se historiken eller ändra det (#77). */
function beslutslank(k: Koppling) {
  return { path: '/redaktion/kopplingar', query: { ...(k.status === 'forslag' ? {} : { status: k.status }), koppling: String(k.id) } }
}

const a = ref<Arende | null>(null)
const laddar = ref(true)
const fel = ref<string | null>(null)

async function ladda() {
  laddar.value = true
  fel.value = null
  try {
    a.value = await hamtaArende(String(route.params.id))
  } catch (e) {
    if (e instanceof EjInloggad) return utloggad()
    fel.value = e instanceof Saknas ? 'Ärendet finns inte.' : e instanceof Error ? e.message : String(e)
  } finally {
    laddar.value = false
  }
}
watch(() => route.params.id, ladda, { immediate: true })

const lank = (s: { id: number }, paragraf: number) => `/politik/sammantraden/${s.id}/paragraf/${paragraf}`
const nyckel = (s: { id: number }, paragraf: number) => `${s.id}:${paragraf}`

/** Kopplingen som för ärendet till behandlingen, från en tidigare behandling i ärendet. */
const inkommande = computed(() => {
  const ut = new Map<string, Koppling[]>()
  if (!a.value) return ut
  const medlemmar = new Set(a.value.behandlingar.map((b) => nyckel(b.sammantrade, b.paragraf)))
  for (const k of a.value.kopplingar) {
    const till = nyckel(k.till.sammantrade, k.till.paragraf)
    if (medlemmar.has(till) && medlemmar.has(nyckel(k.fran.sammantrade, k.fran.paragraf))) {
      ut.set(till, [...(ut.get(till) ?? []), k])
    }
  }
  return ut
})

/** Förslag och avvisade kopplingar till behandlingar utanför ärendet. */
const ovriga = computed(() =>
  (a.value?.kopplingar ?? []).filter((k) => k.status === 'forslag' || k.status === 'avvisad'),
)
</script>

<template>
  <nav class="brodsmulor" aria-label="Brödsmulor">
    <RouterLink to="/politik">Politik och beslut</RouterLink>
    <span aria-hidden="true">›</span>
    <span>Ärende</span>
  </nav>

  <p v-if="laddar">Hämtar uppgifter…</p>
  <p v-else-if="fel" class="fel">{{ fel }}</p>

  <template v-else-if="a">
    <header class="vyhuvud">
      <p class="overrubrik">Ärende · {{ a.behandlingar.length }} behandlingar</p>
      <h1>{{ a.rubrik || 'Rubrik saknas' }}</h1>
      <p v-if="a.diarienummer.length" class="ingress" data-testid="arende-diarienummer">
        Diarienummer {{ a.diarienummer.join(', ') }}
      </p>
      <p class="ingress">
        Ett ärende kan få nya diarienummer när det går vidare till ett annat organ. Behandlingarna kopplas ihop via
        diarienummer och via hänvisningar i beslutsunderlaget.
      </p>
      <p class="markering"><Tolkningsmarkering /></p>
    </header>

    <section class="kort" aria-labelledby="slut-rubrik" data-testid="slutligt-beslut">
      <h2 id="slut-rubrik">Slutligt beslut</h2>
      <template v-if="a.slutligt_beslut">
        <p class="anteckning">
          <RouterLink :to="lank({ id: a.slutligt_beslut.sammantrade_id }, a.slutligt_beslut.paragraf)">
            {{ a.slutligt_beslut.organ.namn }}, {{ sammantradesdatum(a.slutligt_beslut.datum) }} §
            {{ a.slutligt_beslut.paragraf }}
          </RouterLink>
        </p>
        <p class="beslut">{{ a.slutligt_beslut.beslut }}</p>
      </template>
      <p v-else class="saknas">
        Inget slutligt beslut finns i protokollen än. Det senaste beslutet är ett förslag till ett annat organ.
      </p>
    </section>

    <section class="kort" aria-labelledby="vag-rubrik">
      <h2 id="vag-rubrik">Ärendets väg</h2>
      <ol class="vag" data-testid="arendets-vag">
        <li
          v-for="b in a.behandlingar"
          :key="nyckel(b.sammantrade, b.paragraf)"
          data-testid="vag-behandling"
          :data-organ="b.sammantrade.organ.id"
        >
          <p
            v-for="k in inkommande.get(nyckel(b.sammantrade, b.paragraf)) ?? []"
            :key="k.id"
            class="koppling"
            data-testid="vag-koppling"
          >
            <Kopplingsmarkering :koppling="k" />
            <RouterLink v-if="arRedaktor && k.status !== 'automatisk'" :to="beslutslank(k)" class="beslutslank" data-testid="till-beslut">
              Beslutet
            </RouterLink>
          </p>
          <p class="steg">
            <strong>{{ b.sammantrade.organ.namn }}</strong>
            <span class="anteckning">{{ sammantradesdatum(b.sammantrade.datum) }}</span>
          </p>
          <RouterLink :to="lank(b.sammantrade, b.paragraf)" class="stegrubrik">
            § {{ b.paragraf }} {{ b.rubrik }}
          </RouterLink>
          <p v-if="b.diarienummer.length" class="anteckning">
            Diarienummer {{ b.diarienummer.join(', ') }}
            <Kallelsemarkering v-if="b.diarienummer_kallelse" :kalla="b.diarienummer_kallelse" />
          </p>
          <p v-if="b.beslut" class="utdrag">{{ b.beslut }}</p>
        </li>
      </ol>
    </section>

    <section v-if="ovriga.length" class="kort" aria-labelledby="ovr-rubrik" data-testid="ovriga-kopplingar">
      <h2 id="ovr-rubrik">Möjliga kopplingar som inte ingår</h2>
      <p class="ingress">
        Hänvisningar som plattformen inte kunnat koppla säkert. En redaktör bekräftar eller avvisar dem.
      </p>
      <ul class="lista">
        <li v-for="k in ovriga" :key="k.id">
          <RouterLink :to="lank(k.fran.sammantrade, k.fran.paragraf)">
            {{ k.fran.sammantrade.organ.namn }} {{ k.fran.sammantrade.datum }} § {{ k.fran.paragraf }}
          </RouterLink>
          →
          <RouterLink :to="lank(k.till.sammantrade, k.till.paragraf)">
            {{ k.till.sammantrade.organ.namn }} {{ k.till.sammantrade.datum }} § {{ k.till.paragraf }}
          </RouterLink>
          <span class="anteckning"><Kopplingsmarkering :koppling="k" /></span>
          <RouterLink v-if="arRedaktor" :to="beslutslank(k)" class="beslutslank" data-testid="till-beslut">
            {{ k.status === 'forslag' ? 'Besluta' : 'Beslutet' }}
          </RouterLink>
        </li>
      </ul>
    </section>
  </template>
</template>

<style scoped>
.beslutslank {
  font-size: 12px;
  margin-left: 8px;
  color: var(--accent);
}
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
.ingress {
  color: var(--ink-secondary);
  margin: 0 0 4px;
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
.beslut {
  white-space: pre-line;
  max-width: 80ch;
  margin: 0;
}
.saknas {
  color: var(--ink-muted);
  font-style: italic;
  margin: 0;
}
.anteckning {
  font-size: 12px;
  color: var(--ink-muted);
  margin: 0;
}
.vag {
  list-style: none;
  margin: 0;
  padding: 0 0 0 20px;
  border-left: 2px solid var(--line);
}
.vag li {
  position: relative;
  padding: 0 0 20px;
}
.vag li::before {
  content: '';
  position: absolute;
  left: -27px;
  top: 6px;
  width: 10px;
  height: 10px;
  border-radius: 50%;
  background: var(--surface);
  border: 2px solid var(--accent);
}
.vag li:last-child {
  padding-bottom: 0;
}
.koppling {
  margin: 0 0 8px;
}
.steg {
  display: flex;
  gap: 8px;
  align-items: baseline;
  margin: 0;
}
.stegrubrik {
  display: block;
  color: var(--accent);
  margin: 2px 0;
}
.utdrag {
  margin: 4px 0 0;
  max-width: 80ch;
  font-size: 13px;
  color: var(--ink-secondary);
  display: -webkit-box;
  -webkit-line-clamp: 3;
  line-clamp: 3;
  -webkit-box-orient: vertical;
  overflow: hidden;
  white-space: pre-line;
}
.lista {
  list-style: none;
  margin: 12px 0 0;
  padding: 0;
  font-size: 13px;
}
.lista li {
  padding: 6px 0;
  border-bottom: 1px solid var(--line);
}
.lista a {
  color: var(--accent);
}
.lista .anteckning {
  display: block;
}
.fel {
  color: var(--status-critical);
}
</style>
