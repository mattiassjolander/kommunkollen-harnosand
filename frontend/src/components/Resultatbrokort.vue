<script setup lang="ts">
// Hur årets resultat byggs upp ett valt år (#81): skatteintäkter + generella statsbidrag och utjämning
// − verksamhetens nettokostnader ± finansnetto = årets resultat, ur SCB:s resultaträkning.
import { computed } from 'vue'
import type { Resultatbro } from '../api'
import { laddaNer } from '../analys'
import { datum, siffra, tal, visningsskala } from '../format'
import Brodiagram, { type Brosteg } from './Brodiagram.vue'

const props = defineProps<{ bro: Resultatbro; ar: string; vy: 'diagram' | 'tabell' }>()
const emit = defineEmits<{ ar: [string]; vy: ['diagram' | 'tabell'] }>()

const skala = visningsskala('tkr') // mnkr
const data = computed(() => props.bro.ar[props.ar])
const arLista = computed(() => Object.keys(props.bro.ar).sort().reverse())

const kallnamn = (matt: string[]) => {
  const titlar = matt.map((m) => props.bro.matt[m]?.titel ?? m)
  const poster = matt.map((m) => m.split(':')[2]).join(' + ')
  return `${props.bro.matt[matt[0]]?.datakalla.titel ?? 'SCB'} (ResultKnN, post ${poster}): ${titlar.join(', ')}`
}

const steg = computed<Brosteg[]>(() => {
  if (!data.value) return []
  return [
    ...data.value.steg.map((s) => ({
      id: s.id,
      titel: s.titel,
      varde: s.varde * skala.faktor,
      typ: 'del' as const,
      kalla: kallnamn(s.matt),
      markering: s.markering ?? undefined,
    })),
    {
      id: 'resultat',
      titel: 'Årets resultat',
      varde: data.value.resultat * skala.faktor,
      typ: 'summa' as const,
      kalla: kallnamn([props.bro.resultat_matt]),
    },
  ]
})

// Textalternativ: hela räkningen i en mening.
const text = computed(() => {
  if (!data.value) return ''
  const [forsta, ...ovriga] = steg.value.filter((s) => s.typ === 'del')
  const delar = [
    tal(forsta.varde, skala.enhet),
    ...ovriga.map((s) => `${s.varde! < 0 ? 'minus' : 'plus'} ${s.titel.toLowerCase()} ${tal(Math.abs(s.varde!), skala.enhet)}`),
  ]
  return `${props.ar}: ${forsta.titel.toLowerCase()} ${delar.join(', ')} ger årets resultat ${tal(data.value.resultat * skala.faktor, skala.enhet)}.`
})

const avvikelse = computed(() => (data.value ? data.value.kontroll.avvikelse * skala.faktor : 0))

const resultatkalla = computed(() => props.bro.matt[props.bro.resultat_matt])

function exportera() {
  if (!data.value) return
  const rader = ['Steg;Mått-id;År;Värde;Enhet;Källa;Anmärkning']
  const cell = (v: string | number) => (typeof v === 'number' ? String(v).replace('.', ',') : v.includes(';') ? `"${v}"` : v)
  for (const s of data.value.steg)
    rader.push([s.titel, s.matt.join(' + '), props.ar, s.varde, 'tkr', 'SCB', s.markering ?? ''].map(cell).join(';'))
  rader.push(['Årets resultat', props.bro.resultat_matt, props.ar, data.value.resultat, 'tkr', 'SCB', ''].map(cell).join(';'))
  laddaNer(`kommunkollen-resultatbro-${props.ar}.csv`, rader.join('\r\n') + '\r\n')
}
</script>

<template>
  <section class="brokort" data-testid="resultatbro" aria-labelledby="resultatbro-rubrik">
    <div class="huvud">
      <h3 id="resultatbro-rubrik">Så blir årets resultat</h3>
      <div class="val">
        <select
          :value="ar"
          data-testid="bro-ar"
          aria-label="År i brodiagrammet"
          @change="emit('ar', ($event.target as HTMLSelectElement).value)"
        >
          <option v-for="a in arLista" :key="a" :value="a">{{ a }}</option>
        </select>
        <div class="vaxel" role="group" aria-label="Visa brodiagrammet som">
          <button type="button" :aria-pressed="vy === 'diagram'" @click="emit('vy', 'diagram')">Diagram</button>
          <button type="button" :aria-pressed="vy === 'tabell'" @click="emit('vy', 'tabell')">Tabell</button>
        </div>
      </div>
    </div>
    <p class="beskrivning">
      Skatteintäkter och generella statsbidrag och utjämning, minus verksamhetens nettokostnader, plus eller minus
      finansnettot, blir årets resultat. Mnkr ur SCB:s resultaträkning, i löpande priser.
    </p>

    <p v-if="!data" class="beskrivning">Uppgift saknas för {{ ar }}.</p>
    <template v-else>
      <p class="dold" data-testid="brotext">{{ text }}</p>
      <Brodiagram v-if="vy === 'diagram'" :steg="steg" :enhet="skala.enhet" :period="ar" />
      <table v-else class="tabell">
        <caption class="dold">Så blir årets resultat {{ ar }}</caption>
        <thead>
          <tr>
            <th scope="col">Steg</th>
            <th scope="col" class="hoger">{{ skala.enhet }}</th>
            <th scope="col">Källa</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="s in steg" :key="s.id" :class="{ summa: s.typ === 'summa' }">
            <th scope="row">
              {{ s.titel }}
              <span v-if="s.markering" class="markering">{{ s.markering }}</span>
            </th>
            <td class="tal hoger">{{ siffra(s.varde, skala.enhet) }}</td>
            <td class="kalla">{{ s.kalla }}</td>
          </tr>
        </tbody>
      </table>

      <p v-if="avvikelse !== 0" class="avvikelse" data-testid="broavvikelse">
        Delarna summerar till {{ tal(data.kontroll.summa_av_delar * skala.faktor, skala.enhet) }}, men årets resultat
        enligt SCB är {{ tal(data.resultat * skala.faktor, skala.enhet) }}. Avvikelse:
        {{ tal(avvikelse, skala.enhet) }}.
      </p>
      <p v-else class="kontroll" data-testid="brokontroll">
        Kontroll: delarna summerar till årets resultat enligt SCB.
        <template v-if="data.kontroll.restpost">Restposten är skillnaden och är beräknad av Kommunkollen.</template>
      </p>
      <div class="fot">
        <p class="kallrad" data-testid="kallrad">
          Källa:
          <a :href="resultatkalla?.datakalla.url" target="_blank" rel="noopener">{{ resultatkalla?.datakalla.titel }}</a>
          (ResultKnN) · Avser {{ ar }} · Löpande priser · Publicerad {{ datum(resultatkalla?.kallans_publicering ?? null) }}
        </p>
        <RouterLink to="/ekonomi/budget-och-utfall" class="budgetlank" data-testid="bro-budget">Budget och utfall per nämnd</RouterLink>
        <button type="button" class="csv" data-testid="bro-csv" @click="exportera">CSV</button>
      </div>
    </template>
  </section>
</template>

<style scoped>
.brokort {
  background: var(--surface);
  border: 1px solid var(--line);
  border-radius: var(--radius);
  padding: 24px;
  margin-bottom: 16px;
  min-width: 0;
}
.huvud {
  display: flex;
  flex-wrap: wrap;
  justify-content: space-between;
  align-items: flex-start;
  gap: 12px;
}
.val {
  display: flex;
  gap: 8px;
  align-items: center;
}
select {
  font: inherit;
  font-size: 13px;
  padding: 3px 8px;
  border: 1px solid var(--line-strong);
  border-radius: var(--radius);
  background: var(--surface-raised);
  color: var(--ink);
}
.beskrivning {
  color: var(--ink-secondary);
  margin: 4px 0 16px;
  max-width: 70ch;
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
  padding: 4px 10px;
  border: 0;
  background: var(--surface-raised);
  color: var(--ink-secondary);
  cursor: pointer;
}
.vaxel button + button {
  border-left: 1px solid var(--line-strong);
}
.vaxel button[aria-pressed='true'] {
  background: var(--accent-wash);
  color: var(--accent);
  font-weight: 600;
}
.tabell {
  border-collapse: collapse;
  font-size: 13px;
  width: 100%;
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
.tabell tbody th {
  font-weight: 400;
}
.tabell tr.summa th,
.tabell tr.summa td {
  font-weight: 600;
  border-top: 1px solid var(--line-strong);
}
.tabell .kalla {
  font-size: 12px;
  color: var(--ink-muted);
}
.hoger {
  text-align: right !important;
}
.markering {
  display: block;
  font-size: 11px;
  color: var(--ink-muted);
}
.kontroll,
.avvikelse {
  font-size: 13px;
  margin: 12px 0 0;
}
.kontroll {
  color: var(--ink-secondary);
}
.avvikelse {
  padding: 8px 12px;
  border-left: 3px solid var(--status-warning);
  background: var(--page);
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
.csv {
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
.dold {
  position: absolute;
  width: 1px;
  height: 1px;
  overflow: hidden;
  clip: rect(0 0 0 0);
}
</style>
