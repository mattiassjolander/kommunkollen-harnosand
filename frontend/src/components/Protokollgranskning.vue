<script setup lang="ts">
// Redaktionens granskning av ett helt protokoll (#176). En redaktör eller utgivare jämför tolkningen med
// protokollet och markerar det som granskat. En person räcker, eftersom tolkningen är plattformens arbete.
// Rättelser som inte är publicerade spärrar granskningen, och avvikelser ger en varning. Granskningen kan tas
// tillbaka med en motivering, och den upphör om en omtolkning ändrar någon uppgift.
import { ref, watch } from 'vue'
import {
  granskaProtokoll,
  hamtaProtokollgranskning,
  taTillbakaGranskning,
  type Protokollgranskning,
  type Protokollgranskningsrad,
} from '../api'
import { datumTid } from '../format'

const props = defineProps<{ sammantradeId: number }>()
const emit = defineEmits<{ andrat: [] }>()

const g = ref<Protokollgranskning | null>(null)
const fel = ref<string | null>(null)
const motivering = ref('')
const arbetar = ref(false)

async function ladda() {
  try {
    g.value = await hamtaProtokollgranskning(props.sammantradeId)
  } catch (e) {
    fel.value = e instanceof Error ? e.message : String(e)
  }
}
watch(() => props.sammantradeId, ladda, { immediate: true })

async function gor(steg: () => Promise<Protokollgranskning>) {
  fel.value = null
  arbetar.value = true
  try {
    g.value = await steg()
    motivering.value = ''
    emit('andrat')
  } catch (e) {
    fel.value = e instanceof Error ? e.message : String(e)
  } finally {
    arbetar.value = false
  }
}
const granska = () => gor(() => granskaProtokoll(props.sammantradeId))
const taTillbaka = () => gor(() => taTillbakaGranskning(props.sammantradeId, motivering.value))

const FALT: Record<string, string> = {
  rubrik: 'rubriken',
  beslut: 'beslutet',
  diarienummer: 'diarienumret',
  typ: 'typen',
  motionarer: 'motionärerna',
  rost: 'rösten',
  parti: 'partiet',
}
const STATUS: Record<string, string> = { utkast: 'utkast', granskad: 'väntar på publicering' }

function handelse(r: Protokollgranskningsrad): string {
  const granskad = `Granskat av ${r.granskad_av} ${datumTid(r.granskad)}.`
  if (r.status === 'aterkallad')
    return `${granskad} Togs tillbaka av ${r.aterkallad_av} ${datumTid(r.aterkallad)}: ${r.aterkallelse}`
  if (r.status === 'andrad') return `${granskad} Upphörde ${datumTid(r.andrad)}, när tolkningen ändrades.`
  return `${granskad} Gäller.`
}
</script>

<template>
  <section class="kort" aria-labelledby="granskning-rubrik" data-testid="protokollgranskning">
    <h2 id="granskning-rubrik">Granskning för redaktionen</h2>
    <p v-if="fel" class="fel" role="alert">{{ fel }}</p>
    <template v-if="g">
      <p v-if="g.andrad_efter_granskning" class="andrad" role="note" data-testid="andrad-efter-granskning">
        <span aria-hidden="true">!</span> Tolkningen har ändrats efter granskningen
      </p>

      <template v-if="g.gallande">
        <p class="beskrivning" data-testid="granskningsstatus">
          Granskat av {{ g.gallande.granskad_av }} {{ datumTid(g.gallande.granskad) }}. Läsaren ser "Granskad av
          redaktionen" med datumet.
        </p>
        <form class="formular" @submit.prevent="taTillbaka">
          <label class="bred">
            Varför tas granskningen tillbaka?
            <input v-model="motivering" required data-testid="granskning-motivering" />
          </label>
          <button type="submit" :disabled="arbetar || !motivering.trim()" data-testid="ta-tillbaka-granskning">
            Ta tillbaka granskningen
          </button>
        </form>
      </template>

      <template v-else>
        <p class="regel">
          Jämför tolkningen med protokollet: närvarolistan, paragraferna med beslut, yrkanden, voteringar och
          reservationer. Markera protokollet som granskat när du inte har hittat några fel. Fel rättas först med
          rättelser.
        </p>
        <div v-if="g.oppna_rattelser.length" class="sparr" role="note" data-testid="granskning-sparr">
          <strong>Kan inte granskas än.</strong> Protokollet har rättelser som inte är publicerade:
          <ul>
            <li v-for="r in g.oppna_rattelser" :key="r.id">
              {{ r.paragraf !== null ? `§ ${r.paragraf}` : r.namn }}, {{ FALT[r.falt] ?? r.falt }}:
              {{ STATUS[r.status] ?? r.status }}
            </li>
          </ul>
          <RouterLink to="/redaktion/rattelser">Till rättelserna</RouterLink>
        </div>
        <div v-if="g.avvikelser.length" class="varning" role="note" data-testid="granskning-varning">
          <strong>Kontrollera avvikelserna.</strong> De stoppar inte granskningen.
          <ul>
            <li v-for="(a, i) in g.avvikelser" :key="i">{{ a }}</li>
          </ul>
        </div>
        <button type="button" :disabled="arbetar || !g.kan_granskas" data-testid="granska-protokoll" @click="granska">
          Markera protokollet som granskat
        </button>
      </template>

      <h3>Logg</h3>
      <p v-if="!g.logg.length" class="saknas">Protokollet har inte granskats.</p>
      <ul v-else class="lista" data-testid="granskningslogg">
        <li v-for="r in g.logg" :key="r.id" :data-status="r.status">{{ handelse(r) }}</li>
      </ul>
    </template>
  </section>
</template>

<style scoped>
.kort {
  background: var(--surface);
  border: 1px solid var(--line);
  border-radius: var(--radius);
  padding: 16px 24px;
  margin-bottom: 16px;
}
h2 {
  font-size: 15px;
  margin: 0 0 8px;
}
h3 {
  font-size: 14px;
  margin: 16px 0 4px;
}
.beskrivning,
.regel {
  font-size: 13px;
  color: var(--ink-secondary);
  margin: 0 0 8px;
  max-width: 80ch;
}
.regel {
  border-left: 2px solid var(--line-strong);
  padding-left: 8px;
}
.andrad,
.sparr,
.varning {
  font-size: 13px;
  margin: 0 0 12px;
  padding: 8px 12px;
  border: 1px solid var(--line-strong);
  border-radius: var(--radius);
  max-width: 80ch;
}
.andrad,
.varning {
  border-left: 3px solid var(--status-warning);
}
.sparr {
  border-left: 3px solid var(--status-critical);
}
.sparr ul,
.varning ul {
  margin: 4px 0;
  padding-left: 20px;
}
.lista {
  list-style: none;
  padding: 0;
  margin: 0;
  font-size: 13px;
}
.lista li {
  padding: 6px 0;
  border-bottom: 1px solid var(--line);
}
button {
  font: inherit;
  font-size: 13px;
  color: var(--accent);
  background: var(--surface);
  border: 1px solid var(--line-strong);
  border-radius: var(--radius);
  padding: 4px 10px;
  cursor: pointer;
}
button:disabled {
  color: var(--ink-muted);
  cursor: not-allowed;
}
.formular {
  display: flex;
  flex-wrap: wrap;
  gap: 12px;
  align-items: flex-end;
  font-size: 13px;
  color: var(--ink-secondary);
}
.formular label {
  display: grid;
  gap: 4px;
}
.formular .bred {
  flex: 1 1 280px;
}
.formular input {
  font: inherit;
  color: var(--ink);
  background: var(--surface);
  border: 1px solid var(--line);
  border-radius: var(--radius);
  padding: 6px 8px;
}
.saknas {
  color: var(--ink-muted);
  font-style: italic;
  font-size: 13px;
}
.fel {
  color: var(--status-critical);
}
a {
  color: var(--accent);
}
</style>
