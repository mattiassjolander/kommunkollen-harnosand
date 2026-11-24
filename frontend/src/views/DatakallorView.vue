<script setup lang="ts">
import { computed, inject, onMounted, ref, type Ref } from 'vue'
import {
  EjInloggad,
  hamtaDatakallor,
  hamtaKorningslogg,
  hamtaStatus,
  korOmKalla,
  type GlobalStatus,
  type Jag,
  type Kallstatusrad,
  type Korningslogg,
} from '../api'
import { tabelldatum, tal } from '../format'
import StatusMarkering from '../components/StatusMarkering.vue'

const kallor = ref<Kallstatusrad[]>([])
const logg = ref<Korningslogg[]>([])
const status = ref<GlobalStatus | null>(null)
const laddar = ref(true)
const fel = ref<string | null>(null)
const utloggad = inject<() => void>('utloggad', () => {})

const jag = inject<Ref<Jag | null>>('jag', ref(null))
const arRedaktor = computed(() => jag.value?.roller.includes('redaktor') ?? false)

async function ladda() {
  try {
    ;[kallor.value, logg.value, status.value] = await Promise.all([
      hamtaDatakallor(),
      hamtaKorningslogg(),
      hamtaStatus(),
    ])
  } catch (e) {
    if (e instanceof EjInloggad) return utloggad()
    fel.value = e instanceof Error ? e.message : String(e)
  } finally {
    laddar.value = false
  }
}
onMounted(ladda)

// Omkörning av en enskild källa
const korsOm = ref<string | null>(null)
const omkorningsfel = ref<string | null>(null)
async function korOm(id: string) {
  korsOm.value = id
  omkorningsfel.value = null
  try {
    await korOmKalla(id)
    await ladda()
  } catch (e) {
    if (e instanceof EjInloggad) return utloggad()
    omkorningsfel.value = e instanceof Error ? e.message : String(e)
  } finally {
    korsOm.value = null
  }
}

const UTLOSARE = { manuell: 'Manuell', schema: 'Schemalagd' }
</script>

<template>
  <header class="vyhuvud">
    <h1>Datakällor och uppdateringsstatus</h1>
    <p class="ingress">
      När varje källa senast kontrollerades och hämtades, och när källan själv senast publicerade uppgifter. En
      lyckad kontroll betyder inte att det fanns något nytt.
    </p>
  </header>

  <p v-if="laddar">Hämtar uppgifter…</p>
  <p v-else-if="fel" class="fel">Kunde inte hämta uppgifter: {{ fel }}</p>
  <template v-else>
    <section class="kort">
      <h2>Datakällor</h2>
      <table class="tabell" data-testid="datakallor">
        <thead>
          <tr>
            <th scope="col">Datakälla</th>
            <th scope="col">Senaste kontroll</th>
            <th scope="col">Senaste lyckade hämtning</th>
            <th scope="col">Senaste publicerade uppgift</th>
            <th scope="col">Status</th>
            <th v-if="arRedaktor" scope="col"><span class="dold">Åtgärd</span></th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="k in kallor" :key="k.id" :data-kalla="k.id">
            <th scope="row">
              <a :href="k.url" target="_blank" rel="noopener">{{ k.titel }}</a>
            </th>
            <td class="tal">{{ tabelldatum(k.senaste_kontroll) }}</td>
            <td class="tal">{{ tabelldatum(k.senaste_lyckade_hamtning) }}</td>
            <td class="tal">{{ tabelldatum(k.senaste_publicering) }}</td>
            <td>
              <StatusMarkering :status="k.status" />
              <p v-if="k.fel" class="feltext">{{ k.fel }}</p>
            </td>
            <td v-if="arRedaktor">
              <button
                type="button"
                class="knapp"
                :disabled="korsOm !== null"
                :data-testid="`kor-om-${k.id}`"
                @click="korOm(k.id)"
              >
                {{ korsOm === k.id ? 'Kör…' : 'Kör om' }}
              </button>
            </td>
          </tr>
        </tbody>
      </table>
      <p v-if="omkorningsfel" class="fel" role="alert">{{ omkorningsfel }}</p>
    </section>

    <section v-if="status?.sokvektorer" class="kort" data-testid="sokvektorer">
      <h2>Sökningen</h2>
      <p v-if="status.sokvektorer.aktiv" class="ingress">
        {{ tal(status.sokvektorer.med_vektorer) }} av {{ tal(status.sokvektorer.enheter) }} sökbara enheter har
        vektorer för sökning på betydelse, och {{ tal(status.sokvektorer.vantar) }} väntar. Modell:
        {{ status.sokvektorer.modell }}, körs på plattformens egen server.
      </p>
      <p v-else class="ingress">
        Sökning på betydelse är inte aktiverad. Sökningen hittar ord och böjningar i
        {{ tal(status.sokvektorer.enheter) }} sökbara enheter.
      </p>
    </section>

    <section class="kort">
      <h2>Körningslogg</h2>
      <p v-if="!logg.length" class="ingress">Ingen insamling har körts än.</p>
      <table v-else class="tabell" data-testid="korningslogg">
        <thead>
          <tr>
            <th scope="col">Körning</th>
            <th scope="col">Utlöst</th>
            <th scope="col">Datakälla</th>
            <th scope="col">Status</th>
            <th scope="col" class="hoger">Nya</th>
            <th scope="col" class="hoger">Ändrade</th>
            <th scope="col" class="hoger">Oförändrade</th>
            <th scope="col">Fel</th>
          </tr>
        </thead>
        <tbody v-for="k in logg" :key="k.id" class="korning" :data-korning="k.id">
          <tr v-if="!k.kallor.length">
            <td class="tal">{{ tabelldatum(k.startad) }}</td>
            <td>{{ UTLOSARE[k.utlosare] }}</td>
            <td colspan="6"><StatusMarkering :status="k.status" /></td>
          </tr>
          <tr v-for="(r, i) in k.kallor" :key="r.datakalla_id">
            <td class="tal">{{ i === 0 ? tabelldatum(k.startad) : '' }}</td>
            <td>{{ i === 0 ? UTLOSARE[k.utlosare] : '' }}</td>
            <td>{{ r.titel }}</td>
            <td><StatusMarkering :status="r.status" /></td>
            <td class="tal hoger">{{ tal(r.antal_nya) }}</td>
            <td class="tal hoger">{{ tal(r.antal_andrade) }}</td>
            <td class="tal hoger">{{ tal(r.antal_oforandrade) }}</td>
            <td class="feltext">{{ r.fel ?? '' }}</td>
          </tr>
        </tbody>
      </table>
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
.kort {
  background: var(--surface);
  border: 1px solid var(--line);
  border-radius: var(--radius);
  padding: 24px;
  margin-bottom: 24px;
  overflow-x: auto;
}
.kort h2 {
  margin-bottom: 12px;
}
.tabell {
  border-collapse: collapse;
  font-size: 13px;
  width: 100%;
}
.tabell th,
.tabell td {
  padding: 6px 16px 6px 0;
  border-bottom: 1px solid var(--line);
  text-align: left;
  vertical-align: top;
}
.tabell thead th {
  color: var(--ink-secondary);
  font-weight: 600;
  white-space: nowrap;
}
.tabell tbody th {
  font-weight: 600;
}
.tabell tbody th a {
  color: inherit;
}
.korning tr:last-child td {
  border-bottom-color: var(--line-strong);
}
.hoger {
  text-align: right !important;
}
.feltext {
  margin: 4px 0 0;
  font-size: 12px;
  color: var(--ink-secondary);
  max-width: 48ch;
  overflow-wrap: anywhere;
}
.fel {
  color: var(--status-critical);
}
.knapp {
  padding: 4px 12px;
  border-radius: var(--radius);
  border: 1px solid var(--line-strong);
  background: var(--surface-raised);
  color: var(--ink);
  font: inherit;
  font-size: 13px;
  white-space: nowrap;
  cursor: pointer;
}
.knapp:hover:not(:disabled) {
  background: var(--accent-wash);
}
.knapp:disabled {
  cursor: default;
  color: var(--ink-muted);
}
.dold {
  position: absolute;
  width: 1px;
  height: 1px;
  overflow: hidden;
  clip: rect(0 0 0 0);
}
</style>
