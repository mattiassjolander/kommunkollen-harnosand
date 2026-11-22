<script setup lang="ts">
// Fastställ en persons parti under en period (#100, ADR-0006). Perioden sparas som utkast och gäller först när
// en annan person med rollen utgivare har granskat och publicerat den. Med `ersatter` skapas i stället en ny
// version av en granskad eller publicerad period, förifylld från den gamla.
import { ref } from 'vue'
import {
  EjInloggad,
  nyVersionAvPartitillhorighet,
  skapaPartitillhorighet,
  type Partitillhorighet,
} from '../api'

const props = defineProps<{ ledamotId: number; ersatter?: Partitillhorighet }>()
const emit = defineEmits<{ sparad: [Partitillhorighet]; avbryt: []; utloggad: [] }>()

const parti = ref(props.ersatter?.parti ?? '')
const fran = ref(props.ersatter?.fran ?? '')
const till = ref(props.ersatter?.till ?? '')
const motivering = ref('')
const sparar = ref(false)
const fel = ref<string | null>(null)

async function spara() {
  fel.value = null
  sparar.value = true
  const data = { parti: parti.value.trim(), fran: fran.value, till: till.value || null, motivering: motivering.value }
  try {
    const p = props.ersatter
      ? await nyVersionAvPartitillhorighet(props.ersatter.id, data)
      : await skapaPartitillhorighet({ ledamot_id: props.ledamotId, ...data })
    emit('sparad', p)
    if (!props.ersatter) parti.value = fran.value = till.value = motivering.value = ''
  } catch (e) {
    if (e instanceof EjInloggad) return emit('utloggad')
    fel.value = e instanceof Error ? e.message : String(e)
  } finally {
    sparar.value = false
  }
}
</script>

<template>
  <form class="periodformular" data-testid="periodformular" @submit.prevent="spara">
    <div class="rad">
      <label>
        Parti
        <input v-model="parti" type="text" required maxlength="4" size="5" placeholder="S" data-testid="period-parti" />
      </label>
      <label>
        Från och med
        <input v-model="fran" type="date" required data-testid="period-fran" />
      </label>
      <label>
        Till och med
        <input v-model="till" type="date" data-testid="period-till" />
      </label>
    </div>
    <p class="hjalp">Partiets förkortning, eller - för partilös. Lämna slutdatum tomt för tills vidare.</p>
    <label>
      {{ ersatter ? 'Motivering till ändringen' : 'Motivering' }}
      <textarea v-model="motivering" rows="2" required data-testid="period-motivering" />
    </label>
    <p v-if="fel" class="fel" role="alert">{{ fel }}</p>
    <div class="knappar">
      <button type="submit" class="knapp primar" :disabled="sparar" data-testid="spara-period">
        {{ ersatter ? 'Spara ny version som utkast' : 'Spara som utkast' }}
      </button>
      <button v-if="ersatter" type="button" class="knapp" @click="emit('avbryt')">Avbryt</button>
    </div>
  </form>
</template>

<style scoped>
.periodformular {
  display: grid;
  gap: 10px;
  max-width: 640px;
  margin-top: 12px;
}
.rad {
  display: flex;
  flex-wrap: wrap;
  gap: 12px;
}
label {
  display: grid;
  gap: 4px;
  font-size: 13px;
  color: var(--ink-secondary);
}
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
