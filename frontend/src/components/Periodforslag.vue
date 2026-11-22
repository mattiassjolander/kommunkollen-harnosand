<script setup lang="ts">
// Förslag på fastställda partitillhörigheter ur närvarolistorna (#100, del 2). Redaktören går igenom förslagen,
// ändrar parti eller datum där det behövs och bekräftar de valda på en gång. De blir utkast i en batch med en
// gemensam motivering, som går att ändra per rad. En utgivare som inte bekräftade dem granskar och publicerar.
import { computed, onMounted, ref } from 'vue'
import { EjInloggad, hamtaPeriodforslag, skapaPeriodbatch, type Personforslag } from '../api'
import { sammantradesdatum } from '../format'
import Partimarkering from './Partimarkering.vue'

const emit = defineEmits<{ skapade: [batch: number, antal: number]; utloggad: [] }>()

interface Rad {
  nyckel: string
  ledamot: Personforslag['ledamot']
  forslag: Personforslag['perioder'][number]
  vald: boolean
  parti: string
  fran: string
  till: string
  motivering: string
}

const rader = ref<Rad[]>([])
const laddar = ref(true)
const fel = ref<string | null>(null)
const sok = ref('')
const motivering = ref('Enligt närvarolistorna i protokollen under perioden.')
const sparar = ref(false)

async function ladda() {
  laddar.value = true
  try {
    rader.value = (await hamtaPeriodforslag()).flatMap((p) =>
      p.perioder.map((f, i) => ({
        nyckel: `${p.ledamot.id}-${i}`,
        ledamot: p.ledamot,
        forslag: f,
        vald: false,
        parti: f.parti,
        fran: f.fran,
        till: f.till ?? '',
        motivering: '',
      })),
    )
  } catch (e) {
    if (e instanceof EjInloggad) return emit('utloggad')
    fel.value = e instanceof Error ? e.message : String(e)
  } finally {
    laddar.value = false
  }
}
onMounted(ladda)

const synliga = computed(() => {
  const q = sok.value.trim().toLocaleLowerCase('sv')
  return q ? rader.value.filter((r) => r.ledamot.namn.toLocaleLowerCase('sv').includes(q)) : rader.value
})
const valda = computed(() => rader.value.filter((r) => r.vald))
const allaSynligaValda = computed(() => synliga.value.length > 0 && synliga.value.every((r) => r.vald))
function valjSynliga(ja: boolean) {
  for (const r of synliga.value) r.vald = ja
}
const forsta = (r: Rad) => r.ledamot.id !== synliga.value[synliga.value.indexOf(r) - 1]?.ledamot.id

async function bekrafta() {
  fel.value = null
  sparar.value = true
  try {
    const skapade = await skapaPeriodbatch({
      motivering: motivering.value,
      perioder: valda.value.map((r) => ({
        ledamot_id: r.ledamot.id,
        parti: r.parti.trim(),
        fran: r.fran,
        till: r.till || null,
        ...(r.motivering.trim() ? { motivering: r.motivering.trim() } : {}),
      })),
    })
    emit('skapade', skapade[0].batch!, skapade.length)
    await ladda()
  } catch (e) {
    if (e instanceof EjInloggad) return emit('utloggad')
    fel.value = e instanceof Error ? e.message : String(e)
  } finally {
    sparar.value = false
  }
}
</script>

<template>
  <section class="forslag" aria-labelledby="forslag-rubrik" data-testid="periodforslag">
    <h2 id="forslag-rubrik">Förslag <span class="antal">({{ rader.length }})</span></h2>
    <p class="anteckning">
      Räknat ur partiet som närvarolistorna anger, med publicerade rättelser men utan härledda partier, för personer
      som ännu inte har någon period. Ett nytt parti föreslås som en egen period när det står vid minst tre
      sammanträden i följd. Enstaka avvikelser visas som krockar.
    </p>
    <p v-if="laddar">Räknar fram förslag…</p>
    <template v-else>
      <p v-if="!rader.length" class="anteckning">Inga förslag. Alla personer med angivet parti har en period.</p>
      <template v-else>
        <div class="verktyg">
          <label>
            Sök person
            <input v-model="sok" type="search" data-testid="forslag-sok" />
          </label>
          <label class="kryss">
            <input
              type="checkbox"
              :checked="allaSynligaValda"
              data-testid="valj-alla"
              @change="valjSynliga(($event.target as HTMLInputElement).checked)"
            />
            Välj alla som visas
          </label>
        </div>
        <div class="tabellram">
          <table class="tabell">
            <thead>
              <tr>
                <th scope="col"><span class="dold">Välj</span></th>
                <th scope="col">Person</th>
                <th scope="col">Parti</th>
                <th scope="col">Från och med</th>
                <th scope="col">Till och med</th>
                <th scope="col">Belägg</th>
                <th scope="col">Krockar</th>
                <th scope="col">Egen motivering</th>
              </tr>
            </thead>
            <tbody>
              <tr
                v-for="r in synliga"
                :key="r.nyckel"
                data-testid="forslag"
                :data-ledamot="r.ledamot.id"
                :class="{ vald: r.vald }"
              >
                <td>
                  <input v-model="r.vald" type="checkbox" :aria-label="`Välj ${r.ledamot.namn} ${r.forslag.fran}`" data-testid="valj" />
                </td>
                <th scope="row">
                  <RouterLink v-if="forsta(r)" :to="`/politik/ledamoter/${r.ledamot.id}`">{{ r.ledamot.namn }}</RouterLink>
                </th>
                <td><input v-model="r.parti" type="text" size="3" maxlength="4" data-testid="forslag-parti" /></td>
                <td><input v-model="r.fran" type="date" data-testid="forslag-fran" /></td>
                <td><input v-model="r.till" type="date" data-testid="forslag-till" /></td>
                <td class="belagg" data-testid="belagg">
                  <template v-for="(antal, parti) in r.forslag.antal_per_parti" :key="parti">
                    <Partimarkering :parti="String(parti)" /> {{ antal }}
                  </template>
                  <template v-if="r.forslag.utan_parti"> · {{ r.forslag.utan_parti }} utan parti</template>
                  <span v-if="r.forslag.forsta" class="anteckning">
                    · {{ r.forslag.forsta }}<template v-if="r.forslag.sista !== r.forslag.forsta"> – {{ r.forslag.sista }}</template>
                  </span>
                  <RouterLink v-if="r.forslag.exempel" :to="`/politik/sammantraden/${r.forslag.exempel.id}`" class="exempel">
                    exempel
                  </RouterLink>
                </td>
                <td data-testid="krockar">
                  <span v-if="!r.forslag.krockar.length" class="anteckning">–</span>
                  <ul v-else class="krockar">
                    <li v-for="k in r.forslag.krockar" :key="k.id">
                      <RouterLink :to="`/politik/sammantraden/${k.id}`">{{ k.organ.id }} {{ sammantradesdatum(k.datum) }}</RouterLink>
                      <Partimarkering :parti="k.parti" />
                    </li>
                  </ul>
                </td>
                <td><input v-model="r.motivering" type="text" placeholder="Gemensam" data-testid="forslag-motivering" /></td>
              </tr>
            </tbody>
          </table>
        </div>
        <form class="bekrafta" @submit.prevent="bekrafta">
          <label>
            Gemensam motivering
            <textarea v-model="motivering" rows="2" required data-testid="batch-motivering" />
          </label>
          <p v-if="fel" class="fel" role="alert">{{ fel }}</p>
          <button type="submit" class="knapp primar" :disabled="sparar || !valda.length" data-testid="bekrafta-forslag">
            Spara {{ valda.length }} {{ valda.length === 1 ? 'period' : 'perioder' }} som utkast
          </button>
        </form>
      </template>
    </template>
  </section>
</template>

<style scoped>
.forslag {
  background: var(--surface);
  border: 1px solid var(--line);
  border-radius: var(--radius);
  padding: 16px 24px;
  margin-bottom: 32px;
}
.antal {
  color: var(--ink-muted);
  font-weight: 400;
}
.anteckning {
  font-size: 12px;
  color: var(--ink-muted);
  margin: 0 0 8px;
}
.verktyg {
  display: flex;
  gap: 16px;
  align-items: end;
  margin: 12px 0;
  font-size: 13px;
  color: var(--ink-secondary);
}
.verktyg label {
  display: grid;
  gap: 4px;
}
.verktyg .kryss {
  display: flex;
  align-items: center;
  gap: 6px;
}
.tabellram {
  overflow-x: auto;
  max-height: 60vh;
  overflow-y: auto;
}
.tabell {
  border-collapse: collapse;
  font-size: 13px;
  width: 100%;
}
.tabell th,
.tabell td {
  padding: 6px 12px 6px 0;
  border-bottom: 1px solid var(--line);
  text-align: left;
  vertical-align: top;
}
.tabell thead th {
  color: var(--ink-secondary);
  font-weight: 600;
  white-space: nowrap;
  position: sticky;
  top: 0;
  background: var(--surface);
}
.tabell tr.vald {
  background: var(--accent-wash);
}
.belagg {
  white-space: nowrap;
}
.exempel {
  margin-left: 6px;
  color: var(--accent);
}
.krockar {
  list-style: none;
  margin: 0;
  padding: 0;
}
input[type='text'],
input[type='date'],
input[type='search'],
textarea {
  font: inherit;
  font-size: 13px;
  color: var(--ink);
  background: var(--surface);
  border: 1px solid var(--line);
  border-radius: var(--radius);
  padding: 4px 6px;
}
.bekrafta {
  display: grid;
  gap: 10px;
  max-width: 640px;
  margin-top: 16px;
}
.bekrafta label {
  display: grid;
  gap: 4px;
  font-size: 13px;
  color: var(--ink-secondary);
}
.fel {
  margin: 0;
  font-size: 13px;
  color: var(--status-critical);
}
.knapp {
  justify-self: start;
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
.dold {
  position: absolute;
  width: 1px;
  height: 1px;
  overflow: hidden;
  clip: rect(0 0 0 0);
}
</style>
