<script setup lang="ts">
// Redaktionens processer (#152). Redaktionen bestämmer listan: en redaktör lägger till en process, och skillen
// harnosandskollen-styrande-dokument läser in stegen som utkast. En utgivare som inte lagt till processen eller läst in
// stegen granskar och publicerar den som en helhet, eller avvisar den. Steg vars dokument har ändrats står överst tills
// en redaktör har tagit ställning.
import { computed, inject, reactive, ref, type Ref } from 'vue'
import {
  EjInloggad,
  aterkallaProcess,
  avvisaProcess,
  granskaProcess,
  hamtaProcesserForRedaktionen,
  laggTillProcess,
  publiceraProcess,
  taStallningTillProcessteg,
  type Jag,
  type Process,
} from '../../api'
import Processkort from '../../components/Processkort.vue'
import { datum } from '../../format'

const utloggad = inject<() => void>('utloggad', () => {})
const jag = inject<Ref<Jag | null>>('jag', ref(null))
const arRedaktor = computed(() => jag.value?.roller.includes('redaktor') ?? false)
const arUtgivare = computed(() => jag.value?.roller.includes('utgivare') ?? false)

const v = ref<{ processer: Process[]; andrade: Process[] } | null>(null)
const fel = ref<string | null>(null)

async function ladda() {
  fel.value = null
  try {
    v.value = await hamtaProcesserForRedaktionen()
  } catch (e) {
    if (e instanceof EjInloggad) return utloggad()
    fel.value = e instanceof Error ? e.message : String(e)
  }
}
ladda()

const GRANSKNING: Record<string, string> = {
  utkast: 'Utkast',
  granskad: 'Granskad',
  publicerad: 'Publicerad',
  avvisad: 'Avvisad',
  aterkallad: 'Återkallad',
}

const egen = (p: Process) => !!jag.value && (p.redaktorer ?? []).includes(jag.value.epost)
const motivering = reactive<Record<number, string>>({})
const sparar = ref<number | null>(null)
const atgardsfel = reactive<Record<number, string>>({})

async function utfor(p: Process, steg: () => Promise<unknown>) {
  sparar.value = p.id
  delete atgardsfel[p.id]
  try {
    await steg()
    delete motivering[p.id]
    await ladda()
  } catch (e) {
    if (e instanceof EjInloggad) return utloggad()
    atgardsfel[p.id] = e instanceof Error ? e.message : String(e)
  } finally {
    sparar.value = null
  }
}

const ny = reactive({ namn: '', beskrivning: '' })
const nyFel = ref<string | null>(null)
async function laggTill() {
  nyFel.value = null
  try {
    await laggTillProcess(ny.namn, ny.beskrivning)
    ny.namn = ''
    ny.beskrivning = ''
    await ladda()
  } catch (e) {
    if (e instanceof EjInloggad) return utloggad()
    nyFel.value = e instanceof Error ? e.message : String(e)
  }
}
</script>

<template>
  <header class="vyhuvud">
    <h1>Processer</h1>
    <p class="ingress">
      Arbetsgångar ur reglementen och delegationsordningar som redaktionen har valt att beskriva. En redaktör lägger till
      en process på listan, och skillen läser in stegen med citat och källa. En utgivare som inte har lagt till processen
      eller läst in stegen granskar och publicerar den, eller avvisar den. Formatet står i docs/styrande-dokument.md.
      Det publicerade finns under
      <RouterLink to="/politik/styrande-dokument/processer">Styrande dokument → Processer</RouterLink>.
    </p>
  </header>

  <p v-if="fel" class="fel">Kunde inte hämta uppgifter: {{ fel }}</p>
  <p v-else-if="!v">Hämtar uppgifter…</p>
  <template v-else>
    <section v-if="v.andrade.length" class="kort" aria-labelledby="andrade-rubrik" data-testid="andrade">
      <h2 id="andrade-rubrik">Dokumentet har ändrats</h2>
      <p class="not">
        Ett dokument som ett steg citerar har fått en ny version. Läs den nya versionen. Står citatet kvar och håller
        steget, ta ställning så att märkningen tas bort. Annars kör skillen för processen igen.
      </p>
      <div v-for="p in v.andrade" :key="p.id">
        <h3>{{ p.namn }}</h3>
        <Processkort :p="p">
          <template #steg="{ s }">
            <div v-if="s.dokument_andrat && arRedaktor" class="atgarder">
              <button type="button" :disabled="sparar === p.id" data-testid="ta-stallning"
                      @click="utfor(p, () => taStallningTillProcessteg(p.id, s.id))">
                Håller fortfarande
              </button>
            </div>
          </template>
          <p v-if="atgardsfel[p.id]" class="fel">{{ atgardsfel[p.id] }}</p>
        </Processkort>
      </div>
    </section>

    <section v-if="arRedaktor" class="kort" aria-labelledby="ny-rubrik">
      <h2 id="ny-rubrik">Lägg till en process</h2>
      <form class="atgarder" data-testid="ny-process" @submit.prevent="laggTill">
        <label>
          Namn
          <input v-model="ny.namn" type="text" required maxlength="80" data-testid="ny-namn" />
        </label>
        <label class="bred">
          Beskrivning (valfri)
          <input v-model="ny.beskrivning" type="text" data-testid="ny-beskrivning" />
        </label>
        <button type="submit">Lägg till</button>
      </form>
      <p v-if="nyFel" class="fel">{{ nyFel }}</p>
    </section>

    <section class="kort" aria-labelledby="lista-rubrik">
      <h2 id="lista-rubrik">Listan</h2>
      <div v-for="p in v.processer" :key="p.id" class="post" data-testid="processforslag">
        <h3>{{ p.namn }}</h3>
        <p class="not" data-testid="granskning">
          {{ GRANSKNING[p.granskning ?? 'utkast'] }}
          <template v-if="p.skapad_av"> · Tillagd av {{ p.skapad_av }}</template>
          <template v-if="p.steg_inlasta">
            · Steg inlästa {{ datum(p.steg_inlasta) }} av {{ p.redaktorer?.join(', ') }}
          </template>
          <template v-if="p.granskad_av"> · Granskad av {{ p.granskad_av }}</template>
          <template v-if="p.publicerad_av"> · Publicerad av {{ p.publicerad_av }}</template>
          <template v-if="p.avvisning"> · Avvisad: {{ p.avvisning }}</template>
          <template v-if="p.aterkallelse"> · Återkallad: {{ p.aterkallelse }}</template>
        </p>
        <Processkort :p="p">
          <div v-if="arUtgivare" class="atgarder">
            <template v-if="p.granskning === 'utkast' || p.granskning === 'granskad'">
              <span v-if="egen(p)" class="not">Du har lagt till processen eller läst in steg och kan inte själv godkänna den.</span>
              <template v-else-if="p.steg.length">
                <button v-if="p.granskning === 'utkast'" type="button" :disabled="sparar === p.id" data-testid="granska"
                        @click="utfor(p, () => granskaProcess(p.id))">
                  Granskad
                </button>
                <button v-else type="button" :disabled="sparar === p.id" data-testid="publicera"
                        @click="utfor(p, () => publiceraProcess(p.id))">
                  Publicera
                </button>
              </template>
            </template>
            <button v-if="['utkast', 'granskad', 'publicerad'].includes(p.granskning ?? '') && motivering[p.id] === undefined"
                    type="button" data-testid="avvisa" @click="motivering[p.id] = ''">
              {{ p.granskning === 'publicerad' ? 'Återkalla' : 'Avvisa' }}
            </button>
          </div>
          <form v-if="motivering[p.id] !== undefined" class="atgarder"
                @submit.prevent="utfor(p, () => (p.granskning === 'publicerad' ? aterkallaProcess : avvisaProcess)(p.id, motivering[p.id]))">
            <label class="bred">
              Motivering
              <input v-model="motivering[p.id]" type="text" data-testid="motivering" />
            </label>
            <button type="submit" :disabled="sparar === p.id">
              {{ p.granskning === 'publicerad' ? 'Återkalla' : 'Avvisa' }}
            </button>
            <button type="button" @click="delete motivering[p.id]">Avbryt</button>
          </form>
          <p v-if="atgardsfel[p.id]" class="fel">{{ atgardsfel[p.id] }}</p>
        </Processkort>
      </div>
    </section>
  </template>
</template>

<style scoped>
.vyhuvud {
  margin-bottom: 16px;
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
h3 {
  margin: 16px 0 4px;
  font-size: 15px;
}
.atgarder {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  align-items: flex-end;
  margin-top: 8px;
  font-size: 13px;
}
.atgarder label {
  display: flex;
  flex-direction: column;
  gap: 4px;
}
.bred {
  flex: 1 1 240px;
}
.not {
  color: var(--ink-muted);
  font-size: 13px;
  margin: 4px 0 8px;
}
.fel {
  color: var(--status-critical);
}
</style>
