<script setup lang="ts">
import { onMounted, provide, ref } from 'vue'
import { hamtaJag, loggaUt, type Jag } from './api'
import LoggaIn from './views/LoggaIn.vue'

const vyer = [{ till: '/ekonomi', namn: 'Ekonomi' }]

const jag = ref<Jag | null>(null)
const kontrollerad = ref(false)

async function kontrollera() {
  jag.value = await hamtaJag()
  kontrollerad.value = true
}

/** Anropas av vyer som får 401 (t.ex. när sessionen gått ut). */
function utloggad() {
  jag.value = null
}
provide('utloggad', utloggad)

async function loggaUtOchVisaInloggning() {
  await loggaUt()
  jag.value = null
}

onMounted(kontrollera)
</script>

<template>
  <template v-if="kontrollerad">
    <LoggaIn v-if="!jag" @inloggad="kontrollera" />
    <div v-else class="ram">
      <aside class="nav">
        <div class="ordmarke">
          <span class="namn">Kommunkollen</span>
          <span class="ort">Härnösand</span>
        </div>
        <nav aria-label="Huvudvyer">
          <RouterLink v-for="v in vyer" :key="v.till" :to="v.till" class="navlank">{{ v.namn }}</RouterLink>
        </nav>
        <div class="anvandare" data-testid="anvandare">
          <span class="anvnamn">{{ jag.namn }}</span>
          <span class="roller">{{ jag.roller.join(', ') }}</span>
          <button type="button" class="utlank" @click="loggaUtOchVisaInloggning">Logga ut</button>
        </div>
      </aside>
      <main class="innehall">
        <RouterView />
      </main>
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
  background: var(--surface);
  display: flex;
  flex-direction: column;
}
.ordmarke {
  display: flex;
  flex-direction: column;
  margin-bottom: 32px;
}
.namn {
  font-weight: 600;
  font-size: 18px;
}
.ort {
  color: var(--ink-secondary);
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
  margin-top: auto;
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
.utlank {
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
.innehall {
  padding: 32px 48px;
  max-width: 1440px;
}
</style>
