<script setup lang="ts">
import { computed, onMounted, provide, ref } from 'vue'
import { hamtaInloggningsmetod, hamtaJag, loggaUt, type Inloggningsmetod, type Jag } from './api'
import Statusindikator from './components/Statusindikator.vue'
import Hogtidsrad from './components/Hogtidsrad.vue'
import Hogtidssymbol from './components/Hogtidssymbol.vue'
import Temavaljare from './components/Temavaljare.vue'
import { useHogtidstema } from './hogtidstema'
import LoggaIn from './views/LoggaIn.vue'

const vyer = [
  { till: '/', namn: 'Översikt' },
  { till: '/ekonomi', namn: 'Ekonomi' },
  { till: '/floden', namn: 'Ekonomiska flöden' },
  { till: '/undersokningar', namn: 'Undersökningar' },
  { till: '/politik', namn: 'Politik och beslut' },
  { till: '/kalender', namn: 'Kalender' },
  { till: '/kommande', namn: 'Kommande' },
  { till: '/datakallor', namn: 'Datakällor' },
]

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

onMounted(kontrollera)
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
    <div v-else class="ram">
      <aside class="nav">
        <div class="ordmarke">
          <img class="platslogotyp ljus" src="/platsvarumarke/logotyp-bla.png" alt="Härnösand Höga Kusten" />
          <img class="platslogotyp morkt" src="/platsvarumarke/logotyp-vit.png" alt="Härnösand Höga Kusten" />
          <span class="namnrad">
            <span class="namn">Kommunkollen</span>
            <Hogtidssymbol v-if="hogtid?.symbol" :symbol="hogtid.symbol" />
          </span>
        </div>
        <nav aria-label="Huvudvyer">
          <RouterLink v-for="v in vyer" :key="v.till" :to="v.till" class="navlank">{{ v.namn }}</RouterLink>
        </nav>
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
      </aside>
      <div class="kolumn">
        <header class="sidhuvud">
          <Statusindikator />
          <Hogtidsrad v-if="hogtid" :tema="hogtid" />
          <Temavaljare />
        </header>
        <main class="innehall">
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
.nav {
  border-right: 1px solid var(--line);
  padding: 24px 16px;
  background: var(--nav);
  display: flex;
  flex-direction: column;
}
.ordmarke {
  display: flex;
  flex-direction: column;
  gap: 8px;
  margin-bottom: 28px;
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
.avsandare {
  margin-top: auto;
  padding: 0 4px 12px;
  font-size: 12px;
  color: var(--ink-secondary);
}
.avsandare p {
  margin: 8px 0 0;
}
.rundlogotyp {
  width: 72px;
  height: auto;
  display: block;
}
.navlank {
  display: block;
  padding: 8px 12px;
  border-radius: var(--radius);
  color: var(--ink-secondary);
  text-decoration: none;
}
.navlank:hover {
  background: var(--accent-wash);
  color: var(--ink);
}
.navlank.router-link-active {
  background: var(--accent-wash);
  color: var(--accent);
  font-weight: 600;
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
/* Mobilbredd: menyn läggs ovanför innehållet. */
@media (max-width: 720px) {
  .ram {
    grid-template-columns: 1fr;
  }
  .nav {
    border-right: 0;
    border-bottom: 1px solid var(--line);
    padding: 12px 16px;
  }
  .ordmarke {
    flex-direction: row;
    align-items: center;
    margin-bottom: 8px;
  }
  .platslogotyp {
    width: 112px;
  }
  nav {
    display: flex;
    flex-wrap: wrap;
    gap: 2px 4px;
  }
  .navlank {
    padding: 4px 8px;
  }
  .avsandare {
    margin-top: 8px;
    padding-bottom: 8px;
  }
  .rundlogotyp {
    display: none;
  }
  .anvandare {
    flex-direction: row;
    flex-wrap: wrap;
    align-items: baseline;
    gap: 4px 8px;
    padding-top: 8px;
  }
  .lank {
    margin-top: 0;
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
