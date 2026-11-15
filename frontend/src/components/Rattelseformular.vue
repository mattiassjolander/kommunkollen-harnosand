<script setup lang="ts">
// Redaktörens formulär för att rätta en automatiskt tolkad uppgift i en behandling (#33), eller
// partiet för en person i ett sammanträdes närvarolista.
// Rättelsen sparas som utkast och publiceras först när en annan person med rollen utgivare
// har granskat och publicerat den.
import { computed, ref, watch } from 'vue'
import { BEHANDLINGSTYPER, EjInloggad, skapaRattelse, type Behandling, type NyRattelse, type Person } from '../api'

const props = defineProps<{
  behandling?: Behandling
  narvaro?: { sammantrade_id: number; personer: Person[] }
}>()
const emit = defineEmits<{ utloggad: [] }>()

interface Val {
  nyckel: string
  grupp: string
  text: string
  mal: Omit<NyRattelse, 'nytt' | 'motivering'>
  nuvarande: unknown
}

function partival(s: number, personer: Person[]): Val[] {
  // Ett härlett parti räknas som saknat: rättelsen gäller det närvarolistan anger.
  return personer.map((p) => ({
    nyckel: `parti:${p.namn}`, grupp: 'Parti i närvarolistan', text: p.namn,
    nuvarande: p.rattelser?.parti ? p.parti : p.parti_harlett ? null : p.parti,
    mal: { sammantrade_id: s, objekt: 'narvaro', namn: p.namn, falt: 'parti' },
  }))
}

const val = computed<Val[]>(() => {
  if (props.narvaro) return partival(props.narvaro.sammantrade_id, props.narvaro.personer)
  const b = props.behandling
  if (!b) return []
  const s = b.sammantrade.id
  const ut: Val[] = [
    { nyckel: 'rubrik', grupp: 'Behandlingen', text: 'Rubrik', nuvarande: b.rubrik,
      mal: { sammantrade_id: s, objekt: 'behandling', paragraf: b.paragraf, falt: 'rubrik' } },
    { nyckel: 'beslut', grupp: 'Behandlingen', text: 'Beslut', nuvarande: b.beslut,
      mal: { sammantrade_id: s, objekt: 'behandling', paragraf: b.paragraf, falt: 'beslut' } },
    { nyckel: 'diarienummer', grupp: 'Behandlingen', text: 'Diarienummer', nuvarande: b.diarienummer,
      mal: { sammantrade_id: s, objekt: 'behandling', paragraf: b.paragraf, falt: 'diarienummer' } },
    { nyckel: 'typ', grupp: 'Behandlingen', text: 'Typ', nuvarande: b.typ ?? null,
      mal: { sammantrade_id: s, objekt: 'behandling', paragraf: b.paragraf, falt: 'typ' } },
  ]
  for (const v of b.voteringar) {
    for (const r of v.roster) {
      if (!r.namn) continue
      ut.push({ nyckel: `rost:${v.nummer}:${r.namn}`, grupp: `Röster, votering ${v.nummer}`, text: r.namn,
        nuvarande: r.rost,
        mal: { sammantrade_id: s, objekt: 'rost', paragraf: b.paragraf, votering: v.nummer, namn: r.namn, falt: 'rost' } })
    }
  }
  return [...ut, ...partival(s, b.beslutande)]
})
const grupper = computed(() => [...new Set(val.value.map((v) => v.grupp))])

const valt = ref(props.narvaro ? (val.value[0]?.nyckel ?? '') : 'beslut')
const nytt = ref('')
const motivering = ref('')
const sparar = ref(false)
const fel = ref<string | null>(null)
const sparat = ref<number | null>(null)

const aktuellt = computed(() => val.value.find((v) => v.nyckel === valt.value))
const falt = computed(() => aktuellt.value?.mal.falt)
const personer = computed(() => props.narvaro?.personer ?? props.behandling?.beslutande ?? [])
const harlett = computed(() => {
  const p = personer.value.find((x) => `parti:${x.namn}` === valt.value)
  return p?.parti_harlett ? p.parti : null
})

function somText(v: unknown): string {
  if (v === null || v === undefined) return ''
  return Array.isArray(v) ? v.join(', ') : String(v)
}
watch(valt, () => {
  nytt.value = somText(aktuellt.value?.nuvarande ?? harlett.value)
}, { immediate: true })

function varde(): unknown {
  if (falt.value === 'diarienummer') return nytt.value.split(',').map((d) => d.trim()).filter(Boolean)
  if (falt.value === 'parti' || falt.value === 'typ') return nytt.value.trim() || null
  return nytt.value
}

async function spara() {
  if (!aktuellt.value) return
  sparar.value = true
  fel.value = null
  sparat.value = null
  try {
    const r = await skapaRattelse({ ...aktuellt.value.mal, nytt: varde(), motivering: motivering.value })
    sparat.value = r.id
    motivering.value = ''
  } catch (e) {
    if (e instanceof EjInloggad) return emit('utloggad')
    fel.value = e instanceof Error ? e.message : String(e)
  } finally {
    sparar.value = false
  }
}
</script>

<template>
  <form class="formular" data-testid="rattelseformular" @submit.prevent="spara">
    <label>
      Uppgift
      <select v-model="valt" data-testid="rattelse-uppgift">
        <optgroup v-for="g in grupper" :key="g" :label="g">
          <option v-for="v in val.filter((x) => x.grupp === g)" :key="v.nyckel" :value="v.nyckel">{{ v.text }}</option>
        </optgroup>
      </select>
    </label>
    <label>
      Rättat värde
      <select v-if="falt === 'rost'" v-model="nytt" data-testid="rattelse-varde">
        <option value="ja">Ja</option>
        <option value="nej">Nej</option>
        <option value="avstar">Avstår</option>
        <option value="franvarande">Frånvarande</option>
      </select>
      <select v-else-if="falt === 'typ'" v-model="nytt" data-testid="rattelse-varde">
        <option v-for="t in BEHANDLINGSTYPER" :key="t.id" :value="t.id">{{ t.namn }}</option>
        <option value="">Kunde inte klassas</option>
      </select>
      <textarea v-else-if="falt === 'beslut'" v-model="nytt" rows="5" data-testid="rattelse-varde" />
      <input v-else v-model="nytt" type="text" data-testid="rattelse-varde" />
      <span v-if="falt === 'diarienummer'" class="hjalp">Flera nummer skiljs med komma.</span>
      <span v-if="falt === 'parti'" class="hjalp">Förkortning, t.ex. S. Ett streck för partilös, tomt om inget parti.</span>
      <span v-if="falt === 'parti' && harlett" class="hjalp" data-testid="harlett-forslag">
        Närvarolistan anger inget parti. Härlett: {{ harlett }}.
      </span>
    </label>
    <label>
      Motivering
      <textarea
        v-model="motivering"
        rows="2"
        placeholder="Var i protokollet det står, t.ex. sidan 12"
        data-testid="rattelse-motivering"
      />
    </label>
    <div class="rad">
      <button type="submit" class="knapp" :disabled="sparar" data-testid="spara-rattelse">Spara som utkast</button>
      <p v-if="sparat" class="klart" role="status" data-testid="rattelse-sparad">
        Utkastet är sparat. Det publiceras när en utgivare har granskat det.
        <RouterLink to="/politik/rattelser">Till rättelserna</RouterLink>
      </p>
      <p v-if="fel" class="fel" role="alert">{{ fel }}</p>
    </div>
  </form>
</template>

<style scoped>
.formular {
  display: grid;
  gap: 12px;
  max-width: 640px;
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
  font-size: 12px;
  color: var(--ink-muted);
}
.rad {
  display: flex;
  gap: 12px;
  align-items: baseline;
  flex-wrap: wrap;
}
.knapp {
  font: inherit;
  font-size: 13px;
  padding: 6px 14px;
  border-radius: var(--radius);
  border: 1px solid var(--accent);
  background: var(--accent);
  color: var(--surface);
  cursor: pointer;
}
.knapp:disabled {
  opacity: 0.6;
}
.klart,
.fel {
  margin: 0;
  font-size: 13px;
}
.klart a {
  color: var(--accent);
}
.fel {
  color: var(--status-critical);
}
</style>
