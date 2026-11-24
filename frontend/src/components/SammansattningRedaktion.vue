<script setup lang="ts">
// Redaktionens del av Sammansättning (#65): kopplingsförslag mellan valet och ledamotsregistret, och kön och
// födelseår med källa för personer som saknar uppgift. Bara för redaktörer och utgivare. Kön och ålder per
// person visas aldrig för läsare.
import { computed, onMounted, ref } from 'vue'
import {
  avvisaValkoppling,
  bekraftaValkoppling,
  granskaPersonuppgift,
  hamtaPersonuppgifter,
  hamtaSammansattningspersoner,
  hamtaValkopplingar,
  publiceraPersonuppgift,
  skapaPersonuppgift,
  taBortPersonuppgift,
  type Personuppgift,
  type Sammansattningsperson,
  type Valkoppling,
} from '../api'
import Partimarkering from './Partimarkering.vue'

const props = defineProps<{ redaktor: boolean; utgivare: boolean; epost: string | null }>()
const emit = defineEmits<{ andrat: [] }>()

const forslag = ref<Valkoppling[]>([])
const personer = ref<Sammansattningsperson[]>([])
const uppgifter = ref<Personuppgift[]>([])
const fel = ref<string | null>(null)
const ny = ref<{ ledamot_id: number | null; kon: string; fodelsear: string; kalla: string }>({
  ledamot_id: null,
  kon: '',
  fodelsear: '',
  kalla: '',
})

const utanUppgift = computed(() =>
  personer.value.filter((p) => p.kalla === null && !p.vantande_uppgifter.length),
)
const vantande = computed(() => uppgifter.value.filter((u) => u.status === 'utkast' || u.status === 'granskad'))

async function ladda() {
  try {
    ;[forslag.value, personer.value, uppgifter.value] = await Promise.all([
      hamtaValkopplingar('forslag'),
      hamtaSammansattningspersoner(),
      hamtaPersonuppgifter(),
    ])
  } catch (e) {
    fel.value = e instanceof Error ? e.message : String(e)
  }
}
onMounted(ladda)

async function gor(steg: () => Promise<unknown>) {
  fel.value = null
  try {
    await steg()
    await ladda()
    emit('andrat')
  } catch (e) {
    fel.value = e instanceof Error ? e.message : String(e)
  }
}

function spara() {
  const v = ny.value
  if (v.ledamot_id === null) return
  return gor(async () => {
    await skapaPersonuppgift({
      ledamot_id: v.ledamot_id!,
      kon: v.kon || null,
      fodelsear: v.fodelsear ? Number(v.fodelsear) : null,
      kalla: v.kalla,
    })
    ny.value = { ledamot_id: null, kon: '', fodelsear: '', kalla: '' }
  })
}

const KON: Record<string, string> = { K: 'kvinna', M: 'man' }
function valtext(k: Valkoppling): string {
  const roll = k.val.vald ? 'vald' : k.val.ersattare ? 'ersättare' : 'kandidat'
  const delar = [`${roll} ${k.val.valar}`]
  if (k.val.ordning) delar.push(`plats ${k.val.ordning}`)
  if (k.val.kon) delar.push(KON[k.val.kon])
  if (k.val.alder !== null) delar.push(`${k.val.alder} år på valdagen`)
  return delar.join(', ')
}
</script>

<template>
  <section class="kort" aria-labelledby="redaktion-rubrik" data-testid="sammansattning-redaktion">
    <h2 id="redaktion-rubrik">För redaktionen</h2>
    <p class="beskrivning">
      Kön och ålder per person syns bara här. Läsare ser bara den sammanställda statistiken.
    </p>
    <p v-if="fel" class="fel" role="alert">{{ fel }}</p>

    <h3>Kopplingsförslag till valet ({{ forslag.length }})</h3>
    <p class="beskrivning">
      Personer i Valmyndighetens filer som inte kunde kopplas säkert till ledamotsregistret, till exempel på grund av
      mellannamn, dubbelnamn, samma namn i två partier eller ett partibyte.
    </p>
    <p v-if="!forslag.length" class="saknas">Inga förslag väntar.</p>
    <ul v-else class="lista">
      <li v-for="k in forslag" :key="k.id" data-testid="valkoppling" :data-id="k.id">
        <span>
          <strong>{{ k.val.namn }}</strong> <Partimarkering :parti="k.val.parti" /> ({{ valtext(k) }})
          → <RouterLink :to="`/politik/ledamoter/${k.ledamot.id}`">{{ k.ledamot.namn }}</RouterLink>
          <span class="meta">? Förslag, inte bekräftat: {{ k.skal }}</span>
        </span>
        <span v-if="props.redaktor" class="knappar">
          <button type="button" data-testid="bekrafta" @click="gor(() => bekraftaValkoppling(k.id))">Bekräfta</button>
          <button type="button" data-testid="avvisa" @click="gor(() => avvisaValkoppling(k.id))">Avvisa</button>
        </span>
      </li>
    </ul>

    <h3>Kön och födelseår med källa</h3>
    <p class="regel" role="note">
      Ange bara uppgifter som står i en källa, till exempel partiets kandidatlista eller en presentation från
      kommunen, med länk eller dokument och sida. Att gissa kön utifrån namn eller bild är inte tillåtet. Uppgiften
      publiceras först när en utgivare som inte är du har granskat den.
    </p>
    <form v-if="props.redaktor" class="formular" data-testid="uppgiftsformular" @submit.prevent="spara">
      <label>
        Person utan uppgift ({{ utanUppgift.length }})
        <select v-model="ny.ledamot_id" required data-testid="uppgift-person">
          <option :value="null" disabled>Välj person</option>
          <option v-for="p in utanUppgift" :key="p.id" :value="p.id">{{ p.namn }}</option>
        </select>
      </label>
      <label>
        Kön
        <select v-model="ny.kon" data-testid="uppgift-kon">
          <option value="">Anges inte</option>
          <option value="K">Kvinna</option>
          <option value="M">Man</option>
        </select>
      </label>
      <label>
        Födelseår
        <input v-model="ny.fodelsear" inputmode="numeric" pattern="\d{4}" size="6" data-testid="uppgift-fodelsear" />
      </label>
      <label class="bred">
        Källa (länk, eller dokument och sida)
        <input v-model="ny.kalla" required data-testid="uppgift-kalla" />
      </label>
      <button type="submit" data-testid="spara-uppgift">Spara som utkast</button>
    </form>

    <h4>Väntar på granskning ({{ vantande.length }})</h4>
    <p v-if="!vantande.length" class="saknas">Inga uppgifter väntar.</p>
    <ul v-else class="lista">
      <li v-for="u in vantande" :key="u.id" data-testid="personuppgift" :data-status="u.status">
        <span>
          <strong>{{ u.ledamot.namn }}</strong>: {{ u.kon ? KON[u.kon] : 'kön anges inte' }},
          {{ u.fodelsear ? `född ${u.fodelsear}` : 'födelseår anges inte' }}
          <span class="meta">Källa: {{ u.kalla }} · {{ u.status === 'utkast' ? 'Utkast' : 'Granskad' }} av
            {{ u.status === 'utkast' ? u.redaktor : u.granskad_av }}</span>
        </span>
        <span class="knappar">
          <template v-if="props.utgivare && u.redaktor !== props.epost">
            <button v-if="u.status === 'utkast'" type="button" data-testid="granska"
                    @click="gor(() => granskaPersonuppgift(u.id))">Granska</button>
            <button v-else type="button" data-testid="publicera"
                    @click="gor(() => publiceraPersonuppgift(u.id))">Publicera</button>
          </template>
          <button v-if="u.status === 'utkast' && u.redaktor === props.epost" type="button"
                  @click="gor(() => taBortPersonuppgift(u.id))">Ta bort</button>
        </span>
      </li>
    </ul>
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
  margin: 0 0 4px;
}
h3 {
  font-size: 14px;
  margin: 16px 0 4px;
}
h4 {
  font-size: 13px;
  margin: 12px 0 4px;
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
.lista {
  list-style: none;
  padding: 0;
  margin: 0;
  font-size: 13px;
}
.lista li {
  display: flex;
  justify-content: space-between;
  gap: 12px;
  padding: 6px 0;
  border-bottom: 1px solid var(--line);
}
.meta {
  display: block;
  font-size: 12px;
  color: var(--ink-muted);
}
.knappar {
  display: flex;
  gap: 8px;
  align-items: flex-start;
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
.formular select,
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
