<script setup lang="ts">
// Rätta motionärerna för en motion (#78). Redaktören eller utgivaren väljer personer ur personregistret,
// där namnvarianter är ihopslagna, eller anger ett parti utan namn när en partigrupp står bakom motionen.
// Partiet förifylls ur närvaron vid sammanträdet där motionen väcktes, och källan visas. Rättelsen anger
// hela listan och sparas som utkast. En annan person med rollen utgivare publicerar den (ADR-0002).
import { computed, onMounted, ref } from 'vue'
import {
  EjInloggad,
  hamtaLedamoter,
  hamtaMotionarParti,
  skapaRattelse,
  type Ledamotsrad,
  type Motionar,
  type Partiforslag,
} from '../api'
import { sammantradesdatum } from '../format'

const props = defineProps<{
  rubrik: string
  motionarer: Motionar[]
  mal: { sammantrade_id: number; paragraf: number }
}>()
const emit = defineEmits<{ utloggad: []; sparad: [id: number]; avbryt: [] }>()

interface Rad {
  person: { id: number; namn: string } | null
  parti: string
  kalla: Partiforslag['kalla'] | 'tolkning' | null
}

const rader = ref<Rad[]>(
  props.motionarer.map((m) => ({
    person: m.person_id && m.namn ? { id: m.person_id, namn: m.namn } : null,
    parti: m.parti ?? '',
    kalla: 'tolkning',
  })),
)
const register = ref<Ledamotsrad[]>([])
const sok = ref('')
const motivering = ref('')
const fel = ref<string | null>(null)
const sparar = ref(false)

onMounted(async () => {
  try {
    register.value = await hamtaLedamoter()
  } catch (e) {
    if (e instanceof EjInloggad) return emit('utloggad')
    fel.value = e instanceof Error ? e.message : String(e)
  }
})

const traffar = computed(() => {
  const q = sok.value.trim().toLocaleLowerCase('sv')
  if (q.length < 2) return []
  return register.value
    .filter((p) => [p.namn, ...p.andra_namn].some((n) => n.toLocaleLowerCase('sv').includes(q)))
    .slice(0, 8)
})

async function laggTill(p: Ledamotsrad) {
  sok.value = ''
  if (rader.value.some((r) => r.person?.id === p.id)) return
  const rad: Rad = { person: { id: p.id, namn: p.namn }, parti: '', kalla: null }
  rader.value.push(rad)
  try {
    const f = await hamtaMotionarParti(p.id, props.mal.sammantrade_id)
    const r = rader.value.find((x) => x.person?.id === p.id)
    if (r && !r.parti) {
      r.parti = f.parti ?? ''
      r.kalla = f.kalla
    }
  } catch (e) {
    if (e instanceof EjInloggad) return emit('utloggad')
  }
}
function laggTillParti() {
  rader.value.push({ person: null, parti: '', kalla: null })
}

function kallatext(k: Rad['kalla']): string {
  if (k === 'tolkning') return 'enligt tolkningen'
  if (!k) return ''
  if (k.grund === 'narvaro') return 'ur närvaron vid sammanträdet där motionen väcktes'
  if (k.grund === 'samma_protokoll') return 'härlett ur samma protokoll'
  const s = k.sammantrade
  return s ? `härlett ur ${s.organ.namn} ${sammantradesdatum(s.datum)}` : 'härlett ur ett annat protokoll'
}

async function spara() {
  fel.value = null
  if (!rader.value.length) {
    fel.value = 'Ange minst en motionär, en person eller ett parti.'
    return
  }
  sparar.value = true
  try {
    const r = await skapaRattelse({
      sammantrade_id: props.mal.sammantrade_id,
      objekt: 'behandling',
      paragraf: props.mal.paragraf,
      falt: 'motionarer',
      nytt: rader.value.map((x) => ({ person_id: x.person?.id ?? null, parti: x.parti.trim() || null })),
      motivering: motivering.value,
    })
    emit('sparad', r.id)
  } catch (e) {
    if (e instanceof EjInloggad) return emit('utloggad')
    fel.value = e instanceof Error ? e.message : String(e)
  } finally {
    sparar.value = false
  }
}
</script>

<template>
  <form class="formular" data-testid="motionarformular" @submit.prevent="spara">
    <p class="rubrik">Rätta motionärerna för <strong>{{ rubrik }}</strong></p>
    <ul class="rader" data-testid="motionarrader">
      <li v-for="(r, i) in rader" :key="i" data-testid="motionarrad">
        <span class="vem">{{ r.person ? r.person.namn : 'Partiet, utan namn' }}</span>
        <label class="parti">
          Parti
          <input v-model="r.parti" type="text" size="4" :aria-label="`Parti för ${r.person?.namn ?? 'partigruppen'}`" data-testid="motionar-parti" />
        </label>
        <span v-if="r.kalla" class="kalla" data-testid="parti-kalla">{{ kallatext(r.kalla) }}</span>
        <button type="button" class="lank" :aria-label="`Ta bort ${r.person?.namn ?? 'partigruppen'}`" @click="rader.splice(i, 1)">
          Ta bort
        </button>
      </li>
      <li v-if="!rader.length" class="tom">Inga motionärer än.</li>
    </ul>

    <div class="lagg-till">
      <label>
        Lägg till person ur registret
        <input v-model="sok" type="search" placeholder="Sök på namn" autocomplete="off" data-testid="motionar-sok" />
      </label>
      <ul v-if="traffar.length" class="traffar" role="listbox" aria-label="Personer i registret">
        <li v-for="p in traffar" :key="p.id">
          <button type="button" class="traff" data-testid="motionar-traff" @click="laggTill(p)">
            {{ p.namn }}<span v-if="p.parti" class="hjalp"> ({{ p.parti }} senast)</span>
            <span v-if="p.andra_namn.length" class="hjalp">, även {{ p.andra_namn.join(', ') }}</span>
          </button>
        </li>
      </ul>
      <p v-else-if="sok.trim().length >= 2" class="hjalp">Ingen person i registret heter så. Bara personer i registret kan anges.</p>
      <button type="button" class="knapp" data-testid="lagg-till-parti" @click="laggTillParti">Lägg till parti utan namn</button>
    </div>

    <label class="motivering">
      Motivering
      <textarea v-model="motivering" rows="2" required placeholder="Var det står, t.ex. i motionen eller protokollet" data-testid="motionar-motivering" />
    </label>
    <p v-if="fel" class="fel" role="alert">{{ fel }}</p>
    <div class="knappar">
      <button type="submit" class="knapp primar" :disabled="sparar" data-testid="spara-motionarer">Spara som utkast</button>
      <button type="button" class="knapp" @click="emit('avbryt')">Avbryt</button>
    </div>
    <p class="hjalp">Rättelsen publiceras när en annan person med rollen utgivare har granskat den.</p>
  </form>
</template>

<style scoped>
.formular {
  display: grid;
  gap: 10px;
  font-size: 13px;
  padding: 12px 0;
  max-width: 72ch;
}
.rubrik {
  margin: 0;
}
.rader {
  list-style: none;
  margin: 0;
  padding: 0;
  display: grid;
  gap: 6px;
}
.rader li {
  display: flex;
  flex-wrap: wrap;
  align-items: baseline;
  gap: 8px 12px;
}
.vem {
  font-weight: 600;
}
.parti input,
.lagg-till input,
.motivering textarea {
  font: inherit;
  padding: 4px 6px;
  border: 1px solid var(--line-strong);
  border-radius: var(--radius);
  background: var(--surface);
  color: var(--ink);
}
.kalla,
.hjalp,
.tom {
  color: var(--ink-muted);
  font-size: 12px;
}
.lagg-till {
  display: grid;
  gap: 6px;
}
.lagg-till label,
.motivering {
  display: grid;
  gap: 4px;
}
.traffar {
  list-style: none;
  margin: 0;
  padding: 0;
  border: 1px solid var(--line);
  border-radius: var(--radius);
}
.traff {
  font: inherit;
  width: 100%;
  text-align: left;
  padding: 6px 8px;
  border: none;
  border-bottom: 1px solid var(--line);
  background: var(--surface);
  color: var(--ink);
  cursor: pointer;
}
.lank {
  font: inherit;
  font-size: 12px;
  border: none;
  background: none;
  color: var(--accent);
  cursor: pointer;
  padding: 0;
}
.knappar {
  display: flex;
  gap: 8px;
}
.knapp {
  font: inherit;
  font-size: 13px;
  padding: 6px 14px;
  border-radius: var(--radius);
  border: 1px solid var(--line);
  background: var(--surface);
  color: var(--ink);
  cursor: pointer;
  justify-self: start;
}
.knapp.primar {
  background: var(--accent);
  border-color: var(--accent);
  color: var(--surface);
}
.fel {
  color: var(--status-critical);
  margin: 0;
}
</style>
