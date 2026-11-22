<script setup lang="ts">
// Krockar (#100, del 3): närvarolistan anger ett annat parti än personens fastställda partitillhörighet. Perioden
// gäller, men krocken visas tills redaktören har bekräftat den. En bekräftelse blir en rättelse av partiet med
// periodens parti, och anger om felet finns i protokollet eller i inläsningen (#74). Visar krocken ett riktigt
// partibyte ändrar redaktören perioderna på personens sida i stället.
import { computed, inject, onMounted, ref, type Ref } from 'vue'
import { bekraftaKrockar, EjInloggad, hamtaKrockar, type FeletI, type Jag, type Personkrockar } from '../api'
import { sammantradesdatum } from '../format'
import FeletIVal from './FeletIVal.vue'
import Partimarkering from './Partimarkering.vue'

const emit = defineEmits<{ utloggad: [] }>()
const jag = inject<Ref<Jag | null>>('jag', ref(null))
const arRedaktor = computed(() => jag.value?.roller.includes('redaktor') ?? false)

const personer = ref<Personkrockar[]>([])
const laddar = ref(true)
const fel = ref<string | null>(null)
const meddelande = ref<string | null>(null)
const valda = ref<Set<string>>(new Set())
const feletI = ref<FeletI | null>(null)
const motivering = ref('')
const sparar = ref(false)

const nyckel = (k: { sammantrade: { id: number }; namn: string }) => `${k.sammantrade.id}|${k.namn}`
const antal = computed(() => personer.value.reduce((n, p) => n + p.krockar.length, 0))

async function ladda() {
  try {
    personer.value = await hamtaKrockar()
  } catch (e) {
    if (e instanceof EjInloggad) return emit('utloggad')
    fel.value = e instanceof Error ? e.message : String(e)
  } finally {
    laddar.value = false
  }
}
onMounted(ladda)
defineExpose({ ladda })

function vaxla(k: string, ja: boolean) {
  const ny = new Set(valda.value)
  if (ja) ny.add(k)
  else ny.delete(k)
  valda.value = ny
}

async function bekrafta() {
  fel.value = meddelande.value = null
  if (!feletI.value) {
    fel.value = 'Ange om felet finns i protokollet eller i inläsningen.'
    return
  }
  sparar.value = true
  try {
    const krockar = [...valda.value].map((v) => {
      const [id, ...namn] = v.split('|')
      return { sammantrade_id: Number(id), namn: namn.join('|') }
    })
    const skapade = await bekraftaKrockar({ felet_i: feletI.value, motivering: motivering.value, krockar })
    meddelande.value = `${skapade.length} ${skapade.length === 1 ? 'krock är bekräftad' : 'krockar är bekräftade'} som rättelser. De granskas under Rättelser.`
    valda.value = new Set()
    motivering.value = ''
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
  <section class="krockar" aria-labelledby="krock-rubrik" data-testid="krocklista">
    <h2 id="krock-rubrik">Krockar <span class="antal">({{ antal }})</span></h2>
    <p class="anteckning">
      Sammanträden där närvarolistan anger ett annat parti än personens fastställda eller väntande period. Perioden
      gäller. Bekräfta krocken med var felet finns, eller ändra perioderna om det är ett partibyte.
    </p>
    <p v-if="laddar">Hämtar krockar…</p>
    <template v-else>
      <p v-if="meddelande" class="meddelande" role="status" data-testid="krockar-bekraftade">{{ meddelande }}</p>
      <p v-if="!antal" class="anteckning">Inga obekräftade krockar.</p>
      <div v-for="p in personer" :key="p.ledamot.id" class="person" data-testid="krockperson" :data-ledamot="p.ledamot.id">
        <h3>
          <RouterLink :to="`/politik/ledamoter/${p.ledamot.id}`">{{ p.ledamot.namn }}</RouterLink>
          <RouterLink
            v-if="arRedaktor"
            :to="`/politik/ledamoter/${p.ledamot.id}#period-rubrik`"
            class="partibyte"
            data-testid="partibyte"
          >
            Det är ett partibyte – ändra perioderna
          </RouterLink>
        </h3>
        <ul>
          <li v-for="k in p.krockar" :key="nyckel(k)" data-testid="krock" :data-sammantrade="k.sammantrade.id">
            <label>
              <input
                v-if="arRedaktor"
                type="checkbox"
                :checked="valda.has(nyckel(k))"
                data-testid="valj-krock"
                @change="vaxla(nyckel(k), ($event.target as HTMLInputElement).checked)"
              />
              <RouterLink :to="`/politik/sammantraden/${k.sammantrade.id}`">
                {{ k.sammantrade.organ.namn }} {{ sammantradesdatum(k.sammantrade.datum) }}
              </RouterLink>
              · protokollet anger <Partimarkering :parti="k.protokollet" />, perioden
              <Partimarkering :parti="k.period.parti" />
              <span class="anteckning">
                ({{ k.period.fran }} – {{ k.period.till ?? 'tills vidare' }}<template v-if="k.period.status !== 'publicerad'">,
                  {{ k.period.status }}</template>)
              </span>
            </label>
          </li>
        </ul>
      </div>
      <form v-if="arRedaktor && antal" class="bekrafta" data-testid="bekrafta-krockar-formular" @submit.prevent="bekrafta">
        <FeletIVal v-model="feletI" />
        <label>
          Motivering
          <textarea v-model="motivering" rows="2" required data-testid="krock-motivering" />
        </label>
        <p v-if="fel" class="fel" role="alert">{{ fel }}</p>
        <button type="submit" class="knapp" :disabled="sparar || !valda.size" data-testid="bekrafta-krockar">
          Bekräfta {{ valda.size }} {{ valda.size === 1 ? 'krock' : 'krockar' }} som rättelser
        </button>
      </form>
      <p v-else-if="fel" class="fel" role="alert">{{ fel }}</p>
    </template>
  </section>
</template>

<style scoped>
.krockar {
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
.person h3 {
  font-size: 14px;
  margin: 12px 0 4px;
  display: flex;
  gap: 12px;
  align-items: baseline;
}
.person a {
  color: var(--accent);
}
.partibyte {
  font-size: 12px;
  font-weight: 400;
}
.person ul {
  list-style: none;
  margin: 0;
  padding: 0;
  font-size: 13px;
}
.person li {
  padding: 2px 0;
}
.bekrafta {
  display: grid;
  gap: 10px;
  max-width: 640px;
  margin-top: 16px;
  padding-top: 12px;
  border-top: 1px solid var(--line);
}
.bekrafta label {
  display: grid;
  gap: 4px;
  font-size: 13px;
  color: var(--ink-secondary);
}
textarea {
  font: inherit;
  font-size: 14px;
  color: var(--ink);
  background: var(--surface);
  border: 1px solid var(--line);
  border-radius: var(--radius);
  padding: 6px 8px;
}
.meddelande {
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
</style>
