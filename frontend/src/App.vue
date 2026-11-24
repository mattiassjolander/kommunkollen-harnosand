<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, onMounted, provide, ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import {
  hamtaInloggningsmetod,
  hamtaJag,
  hamtaKopplingar,
  hamtaRattelser,
  loggaUt,
  type Inloggningsmetod,
  type Jag,
} from './api'
import Brodsmula from './components/Brodsmula.vue'
import Huvudnavigering from './components/Huvudnavigering.vue'
import Sokruta from './components/Sokruta.vue'
import Statusindikator from './components/Statusindikator.vue'
import Hogtidsrad from './components/Hogtidsrad.vue'
import Hogtidssymbol from './components/Hogtidssymbol.vue'
import Temavaljare from './components/Temavaljare.vue'
import { useHogtidstema } from './hogtidstema'
import LoggaIn from './views/LoggaIn.vue'

const jag = ref<Jag | null>(null)
const metod = ref<Inloggningsmetod | null>(null)
// Inloggningssidan visas när läsning kräver inloggning, när man klickat "Logga in",
// eller när Google-inloggningen kom tillbaka med ett fel.
const visaInloggning = ref(new URLSearchParams(window.location.search).has('fel'))

async function kontrollera() {
  ;[jag.value, metod.value] = await Promise.all([hamtaJag(), hamtaInloggningsmetod()])
  if (jag.value) visaInloggning.value = false
}

const oppenLasning = computed(() => metod.value?.anonym_lasning ?? false)
const kraverInloggning = computed(() => !jag.value && (!oppenLasning.value || visaInloggning.value))

/** Anropas av vyer som får 401 (t.ex. när sessionen gått ut). */
function utloggad() {
  jag.value = null
  visaInloggning.value = true
}
provide('utloggad', utloggad)
provide('jag', jag)

// Högtidstemat ändrar bara ramen: en symbol vid logotypen och en rad i sidhuvudet (design.md, Högtidsteman).
const { tema: hogtid, visaTeman, sattVisaTeman } = useHogtidstema()

async function loggaUtOchStanna() {
  await loggaUt()
  jag.value = null
}

function avbrytInloggning() {
  visaInloggning.value = false
  history.replaceState(null, '', window.location.pathname)
}

// Antal som väntar i Redaktion: rättelser som inte är publicerade och kopplingsförslag.
const roller = computed(() => jag.value?.roller ?? [])
const vantar = ref<Partial<Record<'rattelser' | 'kopplingar', number>>>({})
async function raknaVantande() {
  const r = roller.value
  const ut: typeof vantar.value = {}
  const jobb: Promise<void>[] = []
  if (r.includes('redaktor') || r.includes('utgivare'))
    jobb.push(
      Promise.all([hamtaRattelser('utkast'), hamtaRattelser('granskad')]).then(([a, b]) => {
        ut.rattelser = a.length + b.length
      }),
    )
  if (r.includes('redaktor'))
    jobb.push(
      hamtaKopplingar('forslag').then((k) => {
        ut.kopplingar = k.length
      }),
    )
  await Promise.allSettled(jobb)
  vantar.value = ut
}

// Smal skärm (design.md *Navigering*): navigeringen fälls ihop till en menyknapp i sidhuvudet.
const route = useRoute()
const menyOppen = ref(false)
const menyknapp = ref<HTMLButtonElement | null>(null)
const meny = ref<HTMLElement | null>(null)
async function oppnaMeny() {
  menyOppen.value = true
  await nextTick()
  meny.value?.querySelector<HTMLElement>('a, button')?.focus()
}
function stangMeny(aterstall = true) {
  if (!menyOppen.value) return
  menyOppen.value = false
  if (aterstall) menyknapp.value?.focus()
}
function tangent(e: KeyboardEvent) {
  if (e.key === 'Escape') stangMeny()
}

watch(
  () => route.path,
  () => {
    stangMeny(false)
    // Räknas om när man går till redaktionens vyer, där siffrorna ändras.
    if (roller.value.length && route.path.startsWith('/redaktion')) void raknaVantande()
  },
)
watch(roller, () => void raknaVantande())

onMounted(() => {
  void kontrollera()
  window.addEventListener('keydown', tangent)
})
onBeforeUnmount(() => window.removeEventListener('keydown', tangent))
</script>

<template>
  <template v-if="metod">
    <LoggaIn
      v-if="kraverInloggning"
      :metod="metod"
      :kan-avbryta="oppenLasning"
      @inloggad="kontrollera"
      @avbryt="avbrytInloggning"
    />
    <div v-else class="ram" :class="{ 'meny-oppen': menyOppen }">
      <aside id="navigering" ref="meny" class="nav" aria-label="Navigering">
        <div class="ordmarke">
          <img class="platslogotyp ljus" src="/platsvarumarke/logotyp-bla.png" alt="Härnösand Höga Kusten" />
          <img class="platslogotyp morkt" src="/platsvarumarke/logotyp-vit.png" alt="Härnösand Höga Kusten" />
          <span class="namnrad">
            <span class="namn">Kommunkollen</span>
            <Hogtidssymbol v-if="hogtid?.symbol" :symbol="hogtid.symbol" />
          </span>
          <button type="button" class="stang" aria-label="Stäng menyn" @click="stangMeny()">✕</button>
        </div>
        <div class="lista">
          <Huvudnavigering :roller="roller" :vantar="vantar" @valt="stangMeny(false)" />
        </div>
        <div class="fot">
          <div class="avsandare">
            <img class="rundlogotyp" src="/platsvarumarke/logotyp-rund-bla.png" alt="" />
            <p>Oberoende granskning. Inte en kanal för Härnösands kommun.</p>
          </div>
          <div class="anvandare" data-testid="anvandare">
            <template v-if="jag">
              <span class="anvnamn">{{ jag.namn }}</span>
              <span class="roller">{{ jag.roller.join(', ') }}</span>
              <button type="button" class="lank" @click="loggaUtOchStanna">Logga ut</button>
            </template>
            <button v-else type="button" class="lank" @click="visaInloggning = true">Logga in</button>
          </div>
        </div>
      </aside>
      <div v-if="menyOppen" class="skugga" aria-hidden="true" @click="stangMeny()"></div>
      <div class="kolumn">
        <header class="sidhuvud">
          <button
            ref="menyknapp"
            type="button"
            class="menyknapp"
            aria-controls="navigering"
            :aria-expanded="menyOppen"
            data-testid="menyknapp"
            @click="menyOppen ? stangMeny() : oppnaMeny()"
          >
            <span aria-hidden="true">☰</span> Meny
          </button>
          <Statusindikator />
          <Hogtidsrad v-if="hogtid" :tema="hogtid" />
          <Sokruta />
          <Temavaljare />
        </header>
        <main class="innehall">
          <Brodsmula />
          <RouterView />
        </main>
        <footer class="sidfot">
          <button type="button" class="lank" data-testid="visa-teman" @click="sattVisaTeman(!visaTeman)">
            {{ visaTeman ? 'Visa inte teman' : 'Visa teman' }}
          </button>
        </footer>
      </div>
    </div>
  </template>
</template>

<style scoped>
.ram {
  display: grid;
  grid-template-columns: 220px 1fr;
  min-height: 100vh;
}
/* Navigeringen står still när sidan skrollar. Logotypen och användarrutan syns alltid längst ner,
   och bara länklistan skrollar om den inte får plats (design.md *Navigering*). */
.nav {
  position: sticky;
  top: 0;
  height: 100vh;
  height: 100dvh;
  border-right: 1px solid var(--line);
  padding: 24px 16px 16px;
  background: var(--nav);
  display: flex;
  flex-direction: column;
  min-height: 0;
}
.ordmarke {
  display: flex;
  flex-direction: column;
  gap: 8px;
  margin-bottom: 20px;
  padding: 0 4px;
}
.platslogotyp {
  width: 160px;
  height: auto;
}
.platslogotyp.ljus {
  display: var(--logotyp-ljus);
}
.platslogotyp.morkt {
  display: var(--logotyp-morkt);
}
.namnrad {
  display: flex;
  align-items: center;
  gap: 8px;
}
.namn {
  font-weight: 600;
  font-size: 16px;
}
.lista {
  flex: 1;
  min-height: 0;
  overflow-y: auto;
  margin: 0 -4px;
  padding: 0 4px;
}
.fot {
  flex-shrink: 0;
  padding-top: 12px;
}
.avsandare {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 0 4px 12px;
  font-size: 12px;
  color: var(--ink-secondary);
}
.avsandare p {
  margin: 0;
}
.rundlogotyp {
  width: 44px;
  height: auto;
  flex-shrink: 0;
}
.anvandare {
  border-top: 1px solid var(--line);
  padding-top: 12px;
  display: flex;
  flex-direction: column;
  font-size: 13px;
}
.anvnamn {
  font-weight: 600;
  overflow: hidden;
  text-overflow: ellipsis;
}
.roller {
  color: var(--ink-muted);
  font-size: 12px;
}
.lank {
  align-self: flex-start;
  margin-top: 8px;
  padding: 0;
  border: 0;
  background: none;
  color: var(--accent);
  font: inherit;
  cursor: pointer;
  text-decoration: underline;
}
.stang,
.menyknapp,
.skugga {
  display: none;
}
.kolumn {
  min-width: 0;
}
.sidhuvud {
  /* Blått sidhuvud ur platsvarumärket. Texten i statusindikatorn blir vit. */
  --ink: var(--sidhuvud-ink);
  --ink-secondary: var(--sidhuvud-ink);
  --ink-muted: var(--sidhuvud-ink);
  --accent: var(--sidhuvud-ink);
  background: var(--sidhuvud);
  color: var(--sidhuvud-ink);
  padding: 12px 48px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px 16px;
  flex-wrap: wrap;
}
.innehall {
  padding: 32px 48px;
  max-width: 1440px;
}
.sidfot {
  padding: 16px 48px 24px;
  border-top: 1px solid var(--line);
  font-size: 12px;
  color: var(--ink-secondary);
}
.sidfot .lank {
  margin-top: 0;
}
/* Smal skärm: navigeringen blir en meny som öppnas med en knapp i sidhuvudet. */
@media (max-width: 900px) {
  .ram {
    grid-template-columns: 1fr;
  }
  .nav {
    position: fixed;
    z-index: 20;
    inset: 0 auto 0 0;
    width: min(300px, 85vw);
    border-right: 1px solid var(--line);
    visibility: hidden;
    transform: translateX(-100%);
  }
  .meny-oppen .nav {
    visibility: visible;
    transform: none;
    box-shadow: 0 0 24px rgba(0, 0, 0, 0.2);
  }
  .ordmarke {
    flex-direction: row;
    flex-wrap: wrap;
    align-items: center;
    position: relative;
    padding-right: 36px;
  }
  .platslogotyp {
    width: 120px;
  }
  .stang {
    display: block;
    position: absolute;
    top: 0;
    right: 0;
    width: 32px;
    height: 32px;
    border: 1px solid var(--line);
    border-radius: var(--radius);
    background: var(--surface-raised);
    color: var(--ink);
    cursor: pointer;
  }
  .skugga {
    display: block;
    position: fixed;
    inset: 0;
    z-index: 10;
    background: rgba(0, 0, 0, 0.35);
  }
  .menyknapp {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    padding: 6px 10px;
    border: 1px solid var(--sidhuvud-ink);
    border-radius: var(--radius);
    background: transparent;
    color: var(--sidhuvud-ink);
    font: inherit;
    font-size: 14px;
    cursor: pointer;
  }
  .sidhuvud {
    padding: 12px 16px;
  }
  .innehall {
    padding: 16px;
  }
  .sidfot {
    padding: 12px 16px 16px;
  }
}
</style>
