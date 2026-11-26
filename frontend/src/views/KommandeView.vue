<script setup lang="ts">
// Kommande: ärenden som inte är avslutade, ur ärendespårningen. Ett klick på ett ärende visar mer
// om det, med länkar till protokollen och hänvisningarna i beslutsunderlaget.
import { computed, inject, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import {
  EjInloggad,
  hamtaArendeunderlag,
  hamtaKommande,
  Saknas,
  type Arendeunderlag,
  type Kommande,
  type Kommandearende,
  type Kommandestatus,
  type Markningsid,
} from '../api'
import { parti, sammantradesdatum, tabelldatum, tal } from '../format'
import Tolkningsmarkering from '../components/Tolkningsmarkering.vue'
import Markningar from '../components/Markningar.vue'
import Markningsfilter from '../components/Markningsfilter.vue'

const route = useRoute()
const router = useRouter()
const utloggad = inject<() => void>('utloggad', () => {})

const data = ref<Kommande | null>(null)
const laddar = ref(true)
const fel = ref<string | null>(null)

// Filter och valt ärende speglas i URL:en, så att vyn går att dela.
function fraga(namn: string) {
  return computed<string>({
    get: () => (typeof route.query[namn] === 'string' ? (route.query[namn] as string) : ''),
    set: (v) => router.replace({ query: { ...route.query, [namn]: v || undefined } }),
  })
}
const valdStatus = fraga('status')
const valtOrgan = fraga('organ')
const valt = fraga('arende')
const valdMarkning = fraga('markning')
const markningsantal = computed(
  () => Object.fromEntries((data.value?.markningar ?? []).map((m) => [m.id, m.antal])) as Partial<Record<Markningsid, number>>,
)
const sokning = ref('')

async function ladda() {
  laddar.value = true
  fel.value = null
  try {
    data.value = await hamtaKommande()
  } catch (e) {
    if (e instanceof EjInloggad) return utloggad()
    fel.value = e instanceof Error ? e.message : String(e)
  } finally {
    laddar.value = false
  }
}
onMounted(ladda)

const organ = computed(() => {
  const m = new Map<string, string>()
  for (const a of data.value?.arenden ?? []) m.set(a.senaste.sammantrade.organ.id, a.senaste.sammantrade.organ.namn)
  return [...m.entries()]
})

const visade = computed(() => {
  const q = sokning.value.trim().toLowerCase()
  return (data.value?.arenden ?? []).filter(
    (a) =>
      (!valdStatus.value || a.status === valdStatus.value) &&
      (!valtOrgan.value || a.senaste.sammantrade.organ.id === valtOrgan.value) &&
      (!valdMarkning.value || a.markningar.some((m) => m.id === valdMarkning.value)) &&
      (!q || a.rubrik.toLowerCase().includes(q) || a.diarienummer.some((d) => d.toLowerCase().includes(q))),
  )
})

const statusnamn = computed(
  () => Object.fromEntries((data.value?.statusar ?? []).map((s) => [s.id, s.namn])) as Record<Kommandestatus, string>,
)

function lage(a: Kommandearende): string {
  switch (a.status) {
    case 'motion':
      return `${a.vackt ? 'Väckt' : 'Första behandling'} ${tabelldatum(a.sedan)}, väntar på svar i kommunfullmäktige`
    case 'medborgarforslag':
      return `Första behandling ${tabelldatum(a.sedan)}, väntar på svar`
    case 'forslag':
      return `${a.senaste.sammantrade.organ.namn} föreslog ${tabelldatum(a.sedan)}, väntar på ${a.vantar_pa?.namn.toLowerCase() ?? 'nästa organ'}`
    case 'aterremiss':
      return `Återremitterat av ${a.senaste.sammantrade.organ.namn.toLowerCase()} ${tabelldatum(a.sedan)}`
    case 'bordlaggning':
      return `Bordlagt av ${a.senaste.sammantrade.organ.namn.toLowerCase()} ${tabelldatum(a.sedan)}`
    case 'uppdrag':
      return `Uppdrag från ${a.senaste.sammantrade.organ.namn.toLowerCase()} ${tabelldatum(a.sedan)}${a.frist ? `, återrapport ${a.frist}` : ''}`
  }
}

// Detaljer för det valda ärendet.
const underlag = ref<Arendeunderlag | null>(null)
const laddarUnderlag = ref(false)
const underlagsfel = ref<string | null>(null)

watch(
  valt,
  async (id) => {
    underlag.value = null
    underlagsfel.value = null
    if (!id) return
    laddarUnderlag.value = true
    try {
      underlag.value = await hamtaArendeunderlag(id)
    } catch (e) {
      if (e instanceof EjInloggad) return utloggad()
      underlagsfel.value = e instanceof Saknas ? 'Ärendet finns inte längre.' : e instanceof Error ? e.message : String(e)
    } finally {
      laddarUnderlag.value = false
    }
  },
  { immediate: true },
)

function vaxla(a: Kommandearende) {
  valt.value = valt.value === String(a.arende_id) ? '' : String(a.arende_id)
}

const lank = (sammantradeId: number, paragraf: number) => `/politik/sammantraden/${sammantradeId}/paragraf/${paragraf}`
</script>

<template>
  <header class="vyhuvud">
    <h1>Kommande ärenden</h1>
    <p class="ingress">
      Ärenden som inte är avslutade: obesvarade motioner och medborgarförslag, ärenden som återremitterats eller
      bordlagts, förslag som väntar på beslut i ett annat organ och pågående uppdrag. Uppgifterna är automatiskt lästa
      ur protokollen. Ett ärende kan redan vara avgjort i en behandling som plattformen inte kunnat koppla.
    </p>
    <p class="markering"><Tolkningsmarkering /></p>
  </header>

  <p v-if="laddar">Hämtar uppgifter…</p>
  <p v-else-if="fel" class="fel">Kunde inte hämta uppgifter: {{ fel }}</p>

  <template v-else-if="data">
    <div class="statusval" role="group" aria-label="Visa ärenden med status">
      <button type="button" :class="{ vald: !valdStatus }" data-testid="status-alla" @click="valdStatus = ''">
        Alla <span class="antal">{{ tal(data.arenden.length) }}</span>
      </button>
      <button
        v-for="s in data.statusar.filter((s) => s.antal)"
        :key="s.id"
        type="button"
        :class="{ vald: valdStatus === s.id }"
        :data-testid="`status-${s.id}`"
        @click="valdStatus = valdStatus === s.id ? '' : s.id"
      >
        {{ s.namn }} <span class="antal">{{ tal(s.antal) }}</span>
      </button>
    </div>

    <div class="filter">
      <label>
        Organ
        <select v-model="valtOrgan" data-testid="organ">
          <option value="">Alla organ</option>
          <option v-for="[id, namn] in organ" :key="id" :value="id">{{ namn }}</option>
        </select>
      </label>
      <Markningsfilter v-model="valdMarkning" :antal="markningsantal" arenden />
      <label>
        Sök
        <input v-model="sokning" type="search" placeholder="Rubrik eller diarienummer" data-testid="sok" />
      </label>
    </div>

    <p v-if="!visade.length" class="saknas">Inga pågående ärenden matchar urvalet.</p>
    <ul v-else class="lista" data-testid="kommande">
      <li
        v-for="a in visade"
        :key="a.arende_id"
        :class="{ oppen: valt === String(a.arende_id) }"
        data-testid="kommande-arende"
        :data-status="a.status"
      >
        <button
          type="button"
          class="rad"
          :aria-expanded="valt === String(a.arende_id)"
          :aria-controls="`detalj-${a.arende_id}`"
          @click="vaxla(a)"
        >
          <span class="etikett" :class="a.status">{{ statusnamn[a.status] }}</span>
          <span class="text">
            <span class="rubrik">{{ a.rubrik }}</span>
            <Markningar :markningar="a.markningar" class="chips" />
            <span class="lage">
              {{ lage(a) }}
              <span v-if="a.over_ett_ar" class="varning" title="En motion ska besvaras inom ett år (KL 5 kap. 35 §)">
                · Mer än ett år
              </span>
            </span>
          </span>
          <span class="dagar" :title="`${a.dagar} dagar sedan`">{{ tal(a.dagar) }} d</span>
          <span class="pil" aria-hidden="true">{{ valt === String(a.arende_id) ? '▾' : '▸' }}</span>
        </button>

        <div v-if="valt === String(a.arende_id)" :id="`detalj-${a.arende_id}`" class="detalj" data-testid="detalj">
          <dl class="fakta">
            <div>
              <dt>Status</dt>
              <dd>{{ statusnamn[a.status] }}</dd>
            </div>
            <div v-if="a.vantar_pa">
              <dt>Nästa beslut</dt>
              <dd>{{ a.vantar_pa.namn }}</dd>
            </div>
            <div v-if="a.frist">
              <dt>Återrapport</dt>
              <dd>{{ a.frist }}</dd>
            </div>
            <div v-if="a.diarienummer.length">
              <dt>Diarienummer</dt>
              <dd>{{ a.diarienummer.join(', ') }}</dd>
            </div>
            <div v-if="a.motionarer.length">
              <dt>Motionärer</dt>
              <dd>{{ a.motionarer.map((m) => (m.namn ? `${m.namn} (${parti(m.parti)})` : parti(m.parti))).join(', ') }}</dd>
            </div>
            <div>
              <dt>Behandlingar</dt>
              <dd>{{ a.antal_behandlingar }}</dd>
            </div>
          </dl>

          <h3>Senaste beslutet</h3>
          <p class="anteckning">
            <RouterLink :to="lank(a.senaste.sammantrade.id, a.senaste.paragraf)">
              {{ a.senaste.sammantrade.organ.namn }}, {{ sammantradesdatum(a.senaste.sammantrade.datum) }} §
              {{ a.senaste.paragraf }}
            </RouterLink>
          </p>
          <p class="beslut">{{ a.senaste.beslut || 'Beslutstexten saknas i tolkningen.' }}</p>

          <h3>Handlingar och underlag</h3>
          <p v-if="laddarUnderlag">Hämtar underlag…</p>
          <p v-else-if="underlagsfel" class="fel">{{ underlagsfel }}</p>
          <ol v-else-if="underlag" class="underlag" data-testid="underlag">
            <li v-for="b in underlag.behandlingar" :key="`${b.sammantrade.id}-${b.paragraf}`">
              <p class="steg">
                <strong>{{ b.sammantrade.organ.namn }}</strong>
                <span class="anteckning">{{ sammantradesdatum(b.sammantrade.datum) }}</span>
              </p>
              <RouterLink :to="lank(b.sammantrade.id, b.paragraf)" class="stegrubrik">
                § {{ b.paragraf }} {{ b.rubrik }}
              </RouterLink>
              <p v-if="b.protokoll" class="handlingar" data-testid="protokoll-lankar">
                <a :href="b.protokoll.url" target="_blank" rel="noopener">
                  {{ b.protokoll.typ === 'paragrafprotokoll' ? 'Paragrafprotokoll' : 'Protokoll' }} (harnosand.se)
                </a>
                ·
                <a :href="b.protokoll.kopia" target="_blank" rel="noopener">Sparad kopia (PDF)</a>
              </p>
              <div v-if="b.hanvisningar.length" class="hanvisningar">
                <p class="anteckning">Beslutsunderlag enligt protokollet:</p>
                <ul>
                  <li v-for="(h, i) in b.hanvisningar" :key="i">
                    <RouterLink v-if="h.behandling" :to="lank(h.behandling.sammantrade_id, h.behandling.paragraf)">
                      {{ h.text }}
                    </RouterLink>
                    <span v-else>{{ h.text }}</span>
                  </li>
                </ul>
              </div>
            </li>
          </ol>

          <p class="helt">
            <RouterLink :to="`/politik/arenden/${a.arende_id}`">Visa hela ärendets väg →</RouterLink>
          </p>
        </div>
      </li>
    </ul>
  </template>
</template>

<style scoped>
.chips {
  display: flex;
  margin: 2px 0;
}
.vyhuvud {
  margin-bottom: 24px;
}
.ingress {
  color: var(--ink-secondary);
  margin: 0;
  max-width: 70ch;
}
.markering {
  margin: 12px 0 0;
}
.statusval {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-bottom: 16px;
}
.statusval button {
  font: inherit;
  font-size: 13px;
  padding: 4px 10px;
  border: 1px solid var(--line-strong);
  border-radius: var(--radius);
  background: var(--surface);
  color: var(--ink-secondary);
  cursor: pointer;
}
.statusval button.vald {
  background: var(--accent-wash);
  border-color: var(--accent);
  color: var(--accent);
  font-weight: 600;
}
.antal {
  font-variant-numeric: tabular-nums;
  color: var(--ink-muted);
  margin-left: 4px;
}
.vald .antal {
  color: inherit;
}
.filter {
  display: flex;
  flex-wrap: wrap;
  gap: 16px;
  margin-bottom: 16px;
  font-size: 13px;
}
.filter label {
  display: flex;
  align-items: center;
  gap: 8px;
  color: var(--ink-secondary);
}
.filter input,
.filter select {
  font: inherit;
  padding: 4px 8px;
  border: 1px solid var(--line-strong);
  border-radius: var(--radius);
  background: var(--surface);
  color: var(--ink);
}
.filter input {
  min-width: 240px;
}
.lista {
  list-style: none;
  margin: 0;
  padding: 0;
  background: var(--surface);
  border: 1px solid var(--line);
  border-radius: var(--radius);
}
.lista > li + li {
  border-top: 1px solid var(--line);
}
.lista > li.oppen {
  background: var(--surface);
}
.rad {
  display: grid;
  grid-template-columns: 180px 1fr auto 16px;
  gap: 16px;
  align-items: start;
  width: 100%;
  padding: 12px 16px;
  border: 0;
  background: none;
  font: inherit;
  color: inherit;
  text-align: left;
  cursor: pointer;
}
.rad:hover,
.oppen .rad {
  background: var(--accent-wash);
}
.rad:focus-visible {
  outline: 2px solid var(--accent);
  outline-offset: -2px;
}
.etikett {
  justify-self: start;
  font-size: 12px;
  padding: 1px 6px;
  border: 1px solid var(--line-strong);
  border-radius: var(--radius-mark);
  color: var(--ink-secondary);
  white-space: nowrap;
}
.text {
  display: grid;
  gap: 2px;
  min-width: 0;
}
.rubrik {
  font-weight: 600;
}
.lage {
  font-size: 13px;
  color: var(--ink-secondary);
}
.varning {
  color: var(--status-critical);
}
.dagar {
  font-size: 13px;
  color: var(--ink-muted);
  font-variant-numeric: tabular-nums;
  white-space: nowrap;
}
.pil {
  color: var(--ink-muted);
}
.detalj {
  padding: 8px 16px 20px 212px;
  font-size: 14px;
}
.detalj h3 {
  font-size: 13px;
  margin: 16px 0 4px;
  color: var(--ink-secondary);
}
.fakta {
  display: flex;
  flex-wrap: wrap;
  gap: 8px 32px;
  margin: 0;
}
.fakta dt {
  font-size: 12px;
  color: var(--ink-muted);
}
.fakta dd {
  margin: 0;
}
.beslut {
  white-space: pre-line;
  max-width: 80ch;
  margin: 4px 0 0;
}
.anteckning {
  font-size: 12px;
  color: var(--ink-muted);
  margin: 0;
}
.underlag {
  list-style: none;
  margin: 8px 0 0;
  padding: 0 0 0 20px;
  border-left: 2px solid var(--line);
}
.underlag > li {
  position: relative;
  padding: 0 0 16px;
}
.underlag > li::before {
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
.underlag > li:last-child {
  padding-bottom: 0;
}
.steg {
  display: flex;
  gap: 8px;
  align-items: baseline;
  margin: 0;
}
.stegrubrik {
  display: block;
  margin: 2px 0;
}
.handlingar {
  font-size: 13px;
  margin: 2px 0 0;
}
.hanvisningar ul {
  margin: 2px 0 0;
  padding-left: 18px;
  font-size: 13px;
}
.helt {
  margin: 16px 0 0;
}
a {
  color: var(--accent);
}
.saknas {
  color: var(--ink-muted);
  font-style: italic;
}
.fel {
  color: var(--status-critical);
}
@media (max-width: 900px) {
  .rad {
    grid-template-columns: 1fr auto;
  }
  .rad .etikett {
    grid-column: 1 / -1;
  }
  .pil {
    display: none;
  }
  .detalj {
    padding-left: 16px;
  }
}
</style>
