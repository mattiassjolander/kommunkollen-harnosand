<script setup lang="ts">
// Personerna i fliken Partitillhörighet med filter (#100, del 3): har krockar, saknar fastställd period och väntar
// på granskning. Filtret "saknar fastställd period" ersätter arbetslistan för ledamöter utan parti (#74, del 1).
import { computed, onMounted, ref } from 'vue'
import { EjInloggad, hamtaPeriodpersoner, type Periodperson } from '../api'
import Partimarkering from './Partimarkering.vue'

const emit = defineEmits<{ utloggad: [] }>()

type Filter = 'krockar' | 'saknar' | 'vantar' | 'alla'
const FILTER: { id: Filter; namn: string; passar: (p: Periodperson) => boolean }[] = [
  { id: 'saknar', namn: 'Saknar fastställd period', passar: (p) => !p.publicerade.length },
  { id: 'krockar', namn: 'Har krockar', passar: (p) => p.krockar > 0 },
  { id: 'vantar', namn: 'Väntar på granskning', passar: (p) => p.vantande > 0 },
  { id: 'alla', namn: 'Alla', passar: () => true },
]

const personer = ref<Periodperson[]>([])
const laddar = ref(true)
const fel = ref<string | null>(null)
const filter = ref<Filter>('saknar')
const sok = ref('')

async function ladda() {
  try {
    personer.value = await hamtaPeriodpersoner()
  } catch (e) {
    if (e instanceof EjInloggad) return emit('utloggad')
    fel.value = e instanceof Error ? e.message : String(e)
  } finally {
    laddar.value = false
  }
}
onMounted(ladda)
defineExpose({ ladda })

const antal = (f: Filter) => personer.value.filter(FILTER.find((x) => x.id === f)!.passar).length
const synliga = computed(() => {
  const q = sok.value.trim().toLocaleLowerCase('sv')
  const passar = FILTER.find((x) => x.id === filter.value)!.passar
  return personer.value.filter((p) => passar(p) && (!q || p.ledamot.namn.toLocaleLowerCase('sv').includes(q)))
})
</script>

<template>
  <section class="personer" aria-labelledby="personer-rubrik" data-testid="periodpersoner">
    <h2 id="personer-rubrik">Personer</h2>
    <p v-if="laddar">Hämtar personer…</p>
    <p v-else-if="fel" class="fel" role="alert">{{ fel }}</p>
    <template v-else>
      <div class="verktyg">
        <div class="filter" role="group" aria-label="Filter">
          <button
            v-for="f in FILTER"
            :key="f.id"
            type="button"
            :class="{ aktiv: filter === f.id }"
            :aria-pressed="filter === f.id"
            :data-testid="`filter-${f.id}`"
            @click="filter = f.id"
          >
            {{ f.namn }} <span class="antal">({{ antal(f.id) }})</span>
          </button>
        </div>
        <label>
          Sök person
          <input v-model="sok" type="search" data-testid="person-sok" />
        </label>
      </div>
      <p v-if="!synliga.length" class="anteckning">Inga personer.</p>
      <div v-else class="tabellram">
        <table class="tabell">
          <thead>
            <tr>
              <th scope="col">Person</th>
              <th scope="col">Fastställda perioder</th>
              <th scope="col" class="hoger">Väntar</th>
              <th scope="col" class="hoger">Krockar</th>
              <th scope="col" class="hoger">Sammanträden</th>
              <th scope="col">Senast</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="p in synliga" :key="p.ledamot.id" data-testid="periodperson" :data-ledamot="p.ledamot.id">
              <th scope="row">
                <RouterLink :to="`/politik/ledamoter/${p.ledamot.id}`">{{ p.ledamot.namn }}</RouterLink>
              </th>
              <td>
                <span v-if="!p.publicerade.length" class="saknas">Ingen</span>
                <span v-for="t in p.publicerade" :key="t.id" class="period">
                  <Partimarkering :parti="t.parti" /> {{ t.fran }} – {{ t.till ?? 'tills vidare' }}
                </span>
              </td>
              <td class="tal hoger" data-testid="vantar">{{ p.vantande }}</td>
              <td class="tal hoger" data-testid="antal-krockar">{{ p.krockar }}</td>
              <td class="tal hoger">{{ p.antal_sammantraden }}</td>
              <td class="tal">{{ p.senast ?? '–' }}</td>
            </tr>
          </tbody>
        </table>
      </div>
    </template>
  </section>
</template>

<style scoped>
.personer {
  background: var(--surface);
  border: 1px solid var(--line);
  border-radius: var(--radius);
  padding: 16px 24px;
  margin-bottom: 32px;
}
.verktyg {
  display: flex;
  flex-wrap: wrap;
  gap: 16px;
  align-items: end;
  margin: 8px 0 12px;
  font-size: 13px;
  color: var(--ink-secondary);
}
.verktyg label {
  display: grid;
  gap: 4px;
}
.filter {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}
.filter button {
  font: inherit;
  font-size: 13px;
  padding: 4px 10px;
  border-radius: var(--radius);
  border: 1px solid var(--line-strong);
  background: var(--surface);
  color: var(--ink);
  cursor: pointer;
}
.filter button.aktiv {
  border-color: var(--accent);
  background: var(--accent-wash);
}
.antal {
  color: var(--ink-muted);
}
input {
  font: inherit;
  font-size: 13px;
  color: var(--ink);
  background: var(--surface);
  border: 1px solid var(--line);
  border-radius: var(--radius);
  padding: 4px 6px;
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
  padding: 6px 16px 6px 0;
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
.tabell a {
  color: var(--accent);
}
.hoger {
  text-align: right !important;
}
.period {
  display: block;
}
.saknas {
  color: var(--ink-muted);
  font-style: italic;
}
.anteckning {
  font-size: 12px;
  color: var(--ink-muted);
}
.fel {
  color: var(--status-critical);
}
</style>
