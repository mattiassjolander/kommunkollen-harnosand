<script setup lang="ts">
// Ändra en granskad eller publicerad rättelse (#74, del 3). Redaktören skapar en ny version, förifylld från den
// gamla, med en motivering till ändringen. Den går igenom granskning och publicering som vanligt och ersätter den
// gamla när den publiceras. En utgivare kan i stället återkalla en publicerad rättelse direkt, med motivering.
import { ref } from 'vue'
import {
  aterkallaRattelse,
  BEHANDLINGSTYPER,
  EjInloggad,
  nyVersionAvRattelse,
  type FeletI,
  type Rattelse,
} from '../api'
import { rattelsevarde } from '../format'
import FeletIVal from './FeletIVal.vue'

const props = defineProps<{ rattelse: Rattelse; lage: 'version' | 'aterkalla' }>()
const emit = defineEmits<{ klar: []; avbryt: []; utloggad: [] }>()

function somText(v: unknown): string {
  if (v === null || v === undefined) return ''
  return Array.isArray(v) ? v.join(', ') : String(v)
}
const falt = props.rattelse.falt
const nytt = ref(somText(props.rattelse.nytt))
const feletI = ref<FeletI | null>(props.rattelse.felet_i)
const motivering = ref('')
const sparar = ref(false)
const fel = ref<string | null>(null)

function varde(): unknown {
  if (falt === 'motionarer') return props.rattelse.nytt
  if (falt === 'diarienummer') return nytt.value.split(',').map((d) => d.trim()).filter(Boolean)
  if (falt === 'parti' || falt === 'typ') return nytt.value.trim() || null
  return nytt.value
}

async function spara() {
  fel.value = null
  if (props.lage === 'version' && !feletI.value) {
    fel.value = 'Ange om felet finns i protokollet eller i inläsningen.'
    return
  }
  sparar.value = true
  try {
    if (props.lage === 'version') {
      await nyVersionAvRattelse(props.rattelse.id, { nytt: varde(), motivering: motivering.value, felet_i: feletI.value })
    } else {
      await aterkallaRattelse(props.rattelse.id, motivering.value)
    }
    emit('klar')
  } catch (e) {
    if (e instanceof EjInloggad) return emit('utloggad')
    fel.value = e instanceof Error ? e.message : String(e)
  } finally {
    sparar.value = false
  }
}
</script>

<template>
  <form class="andring" :data-testid="lage === 'version' ? 'ny-version-formular' : 'aterkalla-formular'" @submit.prevent="spara">
    <template v-if="lage === 'version'">
      <label v-if="falt !== 'motionarer'">
        Rättat värde
        <select v-if="falt === 'rost'" v-model="nytt" data-testid="version-varde">
          <option value="ja">Ja</option>
          <option value="nej">Nej</option>
          <option value="avstar">Avstår</option>
          <option value="franvarande">Frånvarande</option>
        </select>
        <select v-else-if="falt === 'typ'" v-model="nytt" data-testid="version-varde">
          <option v-for="t in BEHANDLINGSTYPER" :key="t.id" :value="t.id">{{ t.namn }}</option>
          <option value="">Kunde inte klassas</option>
        </select>
        <textarea v-else-if="falt === 'beslut'" v-model="nytt" rows="5" data-testid="version-varde" />
        <input v-else v-model="nytt" type="text" data-testid="version-varde" />
      </label>
      <p v-else class="hjalp">Motionärerna behålls: {{ rattelsevarde(falt, rattelse.nytt) }}.</p>
      <FeletIVal v-model="feletI" />
    </template>
    <label>
      {{ lage === 'version' ? 'Motivering till ändringen' : 'Varför rättelsen återkallas' }}
      <textarea v-model="motivering" rows="2" required data-testid="andring-motivering" />
    </label>
    <p v-if="lage === 'aterkalla'" class="hjalp">Rättelsen slutar gälla direkt, och tolkningen gäller igen.</p>
    <p v-if="fel" class="fel" role="alert">{{ fel }}</p>
    <div class="knappar">
      <button type="submit" class="knapp primar" :disabled="sparar" data-testid="spara-andring">
        {{ lage === 'version' ? 'Spara ny version som utkast' : 'Återkalla rättelsen' }}
      </button>
      <button type="button" class="knapp" @click="emit('avbryt')">Avbryt</button>
    </div>
  </form>
</template>

<style scoped>
.andring {
  display: grid;
  gap: 10px;
  max-width: 640px;
  margin-top: 12px;
  padding-top: 12px;
  border-top: 1px solid var(--line);
}
label {
  display: grid;
  gap: 4px;
  font-size: 13px;
  color: var(--ink-secondary);
}
select,
input,
textarea {
  font: inherit;
  font-size: 14px;
  color: var(--ink);
  background: var(--surface);
  border: 1px solid var(--line);
  border-radius: var(--radius);
  padding: 6px 8px;
}
.hjalp {
  margin: 0;
  font-size: 12px;
  color: var(--ink-muted);
}
.fel {
  margin: 0;
  font-size: 13px;
  color: var(--status-critical);
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
  border: 1px solid var(--line-strong);
  background: var(--surface);
  color: var(--ink);
  cursor: pointer;
}
.knapp.primar {
  border-color: var(--accent);
  background: var(--accent);
  color: var(--surface);
}
</style>
