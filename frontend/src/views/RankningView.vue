<script setup lang="ts">
// En rankning (#66): placeringen över tid för Härnösand och grannkommunerna (plats 1 överst, bruten linje vid
// metodbyte), delmåtten för det senaste året mot riket och en text om avsändaren, metoden och villkoren.
import { computed, inject, ref, watch, type Ref } from 'vue'
import { useRoute } from 'vue-router'
import {
  EjInloggad,
  hamtaRankning,
  registreraMetodbyte,
  Saknas,
  taBortMetodbyte,
  type Jag,
  type Rankningsdelmatt,
  type Rankningssida,
} from '../api'
import { laddaNer } from '../analys'
import { datum } from '../format'
import { rankningsandring, skillnad2, tal2 } from '../rankning'
import Linjediagram from '../components/Linjediagram.vue'

const route = useRoute()
const r = ref<Rankningssida | null>(null)
const laddar = ref(true)
const fel = ref<string | null>(null)
const saknas = ref(false)
const utloggad = inject<() => void>('utloggad', () => {})
const jag = inject<Ref<Jag | null>>('jag', ref(null))
const arRedaktor = computed(() => !!jag.value?.roller.includes('redaktor'))

async function las() {
  laddar.value = true
  fel.value = null
  saknas.value = false
  try {
    r.value = await hamtaRankning(String(route.params.id))
  } catch (e) {
    if (e instanceof EjInloggad) return utloggad()
    if (e instanceof Saknas) saknas.value = true
    else fel.value = e instanceof Error ? e.message : String(e)
  } finally {
    laddar.value = false
  }
}
watch(() => route.params.id, las, { immediate: true })

const serier = computed(() =>
  (r.value?.kommuner ?? []).map((k) => ({
    namn: k.kommun,
    punkter: k.punkter.map((p) => ({ ar: p.ar, varde: p.placering })),
  })),
)
const ar = computed(() => [...new Set(serier.value.flatMap((s) => s.punkter.map((p) => p.ar)))].sort((a, b) => a - b))
const metodbytesar = computed(() => (r.value?.metodbyten ?? []).map((m) => m.ar))
const visaTabell = ref(false)
const placering = (kommun: string, a: number) =>
  r.value?.kommuner.find((k) => k.kommun === kommun)?.punkter.find((p) => p.ar === a)?.placering ?? null

function exportera() {
  if (!r.value) return
  const rader = [['År', ...serier.value.map((s) => s.namn)].join(';')]
  for (const a of ar.value) rader.push([a, ...serier.value.map((s) => placering(s.namn, a) ?? '')].join(';'))
  rader.push('', `Källa: ${r.value.avsandare} (${r.value.url})`)
  laddaNer(`kommunkollen-rankning-${r.value.id}.csv`, rader.join('\n') + '\n')
}

// Delmåtten i källans grupper, i den ordning de kommer.
const grupper = computed(() => {
  const ut: { grupp: string; delmatt: Rankningsdelmatt[] }[] = []
  for (const d of r.value?.delmatt ?? []) {
    const g = ut.find((x) => x.grupp === d.grupp) ?? ut[ut.push({ grupp: d.grupp, delmatt: [] }) - 1]
    g.delmatt.push(d)
  }
  return ut
})
const visaRiket = computed(() => (r.value?.delmatt ?? []).some((d) => d.riksvarde !== null))
const visaPlacering = computed(() => (r.value?.delmatt ?? []).some((d) => d.placering !== null))

function varde(v: number | null, svar: string | null, enhet: string): string {
  if (v === null && !svar) return 'Uppgift saknas'
  const tal = v === null ? '' : `${tal2(v)}${enhet === 'poäng' ? ' p' : ''}`
  return svar ? `${svar}${tal ? ` (${tal})` : ''}` : tal
}
function forandring(d: Rankningsdelmatt): string {
  const f = d.foregaende
  if (!f) return '–'
  const delar = []
  if (d.varde !== null && f.varde !== null) delar.push(skillnad2(d.varde - f.varde))
  if (d.placering !== null && f.placering !== null) delar.push(`plats ${skillnad2(d.placering - f.placering)}`)
  return delar.length ? `${delar.join(', ')} (mot ${f.ar})` : '–'
}

// Redaktionen registrerar metodbyten.
const nyttAr = ref<number | null>(null)
const nyBeskrivning = ref('')
const sparfel = ref<string | null>(null)
async function spara() {
  if (!r.value || nyttAr.value === null) return
  sparfel.value = null
  try {
    r.value.metodbyten = await registreraMetodbyte(r.value.id, nyttAr.value, nyBeskrivning.value)
    nyttAr.value = null
    nyBeskrivning.value = ''
  } catch (e) {
    sparfel.value = e instanceof Error ? e.message : String(e)
  }
}
async function taBort(a: number) {
  if (!r.value) return
  try {
    r.value.metodbyten = await taBortMetodbyte(r.value.id, a)
  } catch (e) {
    sparfel.value = e instanceof Error ? e.message : String(e)
  }
}
</script>

<template>
  <p class="tillbaka"><RouterLink to="/rankningar">‹ Rankningar</RouterLink></p>
  <p v-if="laddar">Hämtar uppgifter…</p>
  <p v-else-if="saknas">Rankningen finns inte.</p>
  <p v-else-if="fel" class="fel">Kunde inte hämta uppgifter: {{ fel }}</p>

  <template v-else-if="r">
    <header class="vyhuvud">
      <h1>{{ r.titel }}</h1>
      <p class="ingress" data-testid="avsandare">
        En rankning av {{ r.avsandare }} ({{ r.avsandartyp.toLowerCase() }}).
        <template v-if="r.senaste">
          Härnösand {{ r.senaste.ar }}: plats {{ r.senaste.placering
          }}<template v-if="r.senaste.antal"> av {{ r.senaste.antal }}</template><template
            v-if="r.senaste.poang !== null"
            >, {{ tal2(r.senaste.poang) }}<template v-if="r.senaste.max_poang !== null">
              av {{ tal2(r.senaste.max_poang) }}</template
            >
            poäng</template
          >.
          <template v-if="r.senaste.foregaende">
            {{ r.senaste.foregaende.ar }}: plats {{ r.senaste.foregaende.placering }}.
            {{ rankningsandring(r.senaste.andring) }}.
          </template>
        </template>
      </p>
    </header>

    <section class="kort sektion" aria-labelledby="placering-rubrik">
      <div class="huvud">
        <h2 id="placering-rubrik">Placering över tid</h2>
        <div class="vaxel" role="group" aria-label="Visning">
          <button type="button" :aria-pressed="!visaTabell" @click="visaTabell = false">Diagram</button>
          <button type="button" :aria-pressed="visaTabell" data-testid="visa-tabell" @click="visaTabell = true">
            Tabell
          </button>
        </div>
      </div>
      <p class="forklaring">Plats 1 står överst. Linjen bryts vid ett metodbyte, då placeringarna före och efter inte går
        att jämföra.</p>
      <Linjediagram
        v-if="!visaTabell && serier.length"
        :serier="serier"
        enhet=""
        :kalla="`Källa: ${r.avsandare}`"
        :etikett="`${r.titel}: placering per år för Härnösand och grannkommunerna`"
        omvand
        :brott="metodbytesar"
      />
      <div v-else-if="serier.length" class="tabellyta">
        <table class="tabell" data-testid="placeringstabell">
          <thead>
            <tr>
              <th scope="col">År</th>
              <th v-for="s in serier" :key="s.namn" scope="col" class="hoger">{{ s.namn }}</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="a in [...ar].reverse()" :key="a">
              <th scope="row">{{ a }}<span v-if="metodbytesar.includes(a)" class="metodmarkering"> · metodbyte</span></th>
              <td v-for="s in serier" :key="s.namn" class="hoger" :class="{ saknas: placering(s.namn, a) === null }">
                {{ placering(s.namn, a) ?? 'Uppgift saknas' }}
              </td>
            </tr>
          </tbody>
        </table>
      </div>
      <div class="fot">
        <p class="kallrad" data-testid="kallrad">
          Källa: {{ r.avsandare }},
          <a :href="r.url" target="_blank" rel="noopener">{{ r.datakalla.titel }}</a>
          <template v-if="ar.length"> · Avser {{ ar[0] }}–{{ ar[ar.length - 1] }}</template> · Hämtad
          {{ datum(r.hamtad) }}
        </p>
        <button type="button" class="csv" data-testid="csv" @click="exportera">CSV</button>
      </div>

      <div v-if="r.metodbyten.length || arRedaktor" class="metodbyten" data-testid="metodbyten">
        <h3>Metodbyten</h3>
        <ul v-if="r.metodbyten.length">
          <li v-for="m in r.metodbyten" :key="m.ar">
            <strong>{{ m.ar }}:</strong> {{ m.beskrivning }}
            <button v-if="arRedaktor" type="button" class="lankknapp" @click="taBort(m.ar)">Ta bort</button>
          </li>
        </ul>
        <p v-else class="forklaring">Inga metodbyten är registrerade.</p>
        <form v-if="arRedaktor" class="metodform" @submit.prevent="spara">
          <label>År <input v-model.number="nyttAr" type="number" min="1900" max="2200" required /></label>
          <label class="vid">Vad ändrades i metoden
            <input v-model="nyBeskrivning" type="text" required />
          </label>
          <button type="submit">Registrera metodbyte</button>
          <p v-if="sparfel" class="fel">{{ sparfel }}</p>
        </form>
      </div>
    </section>

    <section v-if="r.senaste && grupper.length" class="kort sektion" aria-labelledby="delmatt-rubrik">
      <h2 id="delmatt-rubrik">Delmått {{ r.senaste.ar }}</h2>
      <p class="forklaring">
        Härnösands värden för det senaste året, så som {{ r.avsandare }} redovisar dem<template v-if="visaRiket">, med
          värdet för riket</template
        >. Ett delmått som avser ett tidigare år visas med sitt år.
      </p>
      <div class="tabellyta">
        <table class="tabell delmatt" data-testid="delmatt">
          <thead>
            <tr>
              <th scope="col">Delmått</th>
              <th scope="col" class="hoger">År</th>
              <th scope="col" class="hoger">Härnösand</th>
              <th v-if="visaRiket" scope="col" class="hoger">Riket</th>
              <th v-if="visaPlacering" scope="col" class="hoger">Placering</th>
              <th scope="col" class="hoger">Förändring mot året innan</th>
            </tr>
          </thead>
          <tbody v-for="g in grupper" :key="g.grupp">
            <tr v-if="g.grupp" class="gruppnamn">
              <th :colspan="4 + (visaRiket ? 1 : 0) + (visaPlacering ? 1 : 0)" scope="rowgroup">{{ g.grupp }}</th>
            </tr>
            <tr v-for="d in g.delmatt" :key="d.id">
              <th scope="row" class="namn">{{ d.namn }}</th>
              <td class="hoger">{{ d.ar }}</td>
              <td class="hoger" :class="{ saknas: d.varde === null && !d.svar }">
                {{ varde(d.varde, d.svar, d.enhet) }}
              </td>
              <td v-if="visaRiket" class="hoger" :class="{ saknas: d.riksvarde === null }">
                {{ d.riksvarde === null ? 'Uppgift saknas' : tal2(d.riksvarde) }}
              </td>
              <td v-if="visaPlacering" class="hoger">{{ d.placering ?? '–' }}</td>
              <td class="hoger">{{ forandring(d) }}</td>
            </tr>
          </tbody>
        </table>
      </div>
      <p class="kallrad">
        Källa: {{ r.avsandare }},
        <a :href="r.url" target="_blank" rel="noopener">{{ r.datakalla.titel }}</a>
        · Avser {{ r.senaste.ar }} · Hämtad {{ datum(r.hamtad) }}
      </p>
    </section>

    <section class="kort sektion om" aria-labelledby="om-rubrik" data-testid="om-rankningen">
      <h2 id="om-rubrik">Om rankningen</h2>
      <dl>
        <dt>Avsändare</dt>
        <dd>{{ r.avsandare }}, {{ r.avsandartyp.toLowerCase() }}.</dd>
        <dt>Vad som mäts</dt>
        <dd>{{ r.beskrivning }}</dd>
        <dt>Metod</dt>
        <dd><a :href="r.metod_url" target="_blank" rel="noopener">{{ r.avsandare }}s beskrivning av metoden</a></dd>
        <dt>Användarvillkor</dt>
        <dd>{{ r.villkor }}</dd>
      </dl>
      <p class="forklaring">
        Uppgifterna är {{ r.avsandare }}s egna och publiceras som de hämtas. Kommunkollen gör inga egna bedömningar av vad
        en placering betyder.
      </p>
    </section>
  </template>
</template>

<style scoped>
.tillbaka {
  margin: 0 0 8px;
  font-size: 13px;
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
.kort {
  background: var(--surface);
  border: 1px solid var(--line);
  border-radius: var(--radius);
  padding: 24px;
  min-width: 0;
}
.sektion {
  margin-bottom: 24px;
}
.huvud {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 12px;
}
.forklaring {
  font-size: 13px;
  color: var(--ink-secondary);
  max-width: 80ch;
}
.vaxel {
  display: inline-flex;
  border: 1px solid var(--line-strong);
  border-radius: var(--radius);
  overflow: hidden;
}
.vaxel button {
  font: inherit;
  font-size: 12px;
  padding: 2px 10px;
  border: 0;
  background: var(--surface-raised);
  color: var(--ink-secondary);
  cursor: pointer;
}
.vaxel button[aria-pressed='true'] {
  background: var(--accent-wash);
  color: var(--accent);
  font-weight: 600;
}
.fot {
  display: flex;
  justify-content: space-between;
  align-items: flex-end;
  gap: 12px;
}
.kallrad {
  font-size: 12px;
  color: var(--ink-muted);
  margin: 12px 0 0;
}
.kallrad a {
  color: inherit;
}
.csv,
.metodform button {
  flex-shrink: 0;
  font: inherit;
  font-size: 12px;
  padding: 2px 8px;
  border: 1px solid var(--line-strong);
  border-radius: var(--radius);
  background: var(--surface-raised);
  color: var(--ink-secondary);
  cursor: pointer;
}
.csv:hover,
.metodform button:hover {
  background: var(--accent-wash);
}
.tabellyta {
  overflow-x: auto;
}
.tabell {
  border-collapse: collapse;
  font-size: 13px;
  width: 100%;
  font-variant-numeric: tabular-nums;
}
.tabell th,
.tabell td {
  padding: 4px 12px 4px 0;
  border-bottom: 1px solid var(--line);
  text-align: left;
  vertical-align: top;
}
.tabell thead th {
  color: var(--ink-secondary);
  font-weight: 600;
}
.tabell th[scope='row'] {
  font-weight: 400;
}
.delmatt .namn {
  max-width: 60ch;
}
.gruppnamn th {
  padding-top: 16px;
  font-weight: 600;
  color: var(--ink-secondary);
}
.hoger {
  text-align: right !important;
  white-space: nowrap;
}
.saknas {
  color: var(--ink-muted);
  font-style: italic;
}
.metodmarkering {
  color: var(--ink-muted);
  font-size: 12px;
}
.metodbyten {
  margin-top: 20px;
  border-top: 1px solid var(--line);
  padding-top: 12px;
}
.metodbyten h3 {
  font-size: 14px;
  margin: 0 0 8px;
}
.metodbyten ul {
  margin: 0 0 8px;
  padding-left: 18px;
  font-size: 13px;
}
.metodform {
  display: flex;
  flex-wrap: wrap;
  gap: 8px 12px;
  align-items: flex-end;
  font-size: 13px;
}
.metodform label {
  display: flex;
  flex-direction: column;
  gap: 2px;
}
.metodform .vid {
  flex: 1 1 280px;
}
.metodform input {
  font: inherit;
  padding: 2px 6px;
  border: 1px solid var(--line-strong);
  border-radius: var(--radius);
  background: var(--surface);
  color: var(--ink);
}
.lankknapp {
  font: inherit;
  font-size: 12px;
  background: none;
  border: 0;
  color: var(--accent);
  cursor: pointer;
  text-decoration: underline;
}
.om dl {
  display: grid;
  grid-template-columns: max-content 1fr;
  gap: 8px 16px;
  font-size: 13px;
  margin: 0 0 12px;
}
.om dt {
  color: var(--ink-muted);
}
.om dd {
  margin: 0;
  max-width: 80ch;
}
@media (max-width: 700px) {
  .om dl {
    grid-template-columns: 1fr;
  }
}
.fel {
  color: var(--status-critical);
}
</style>
