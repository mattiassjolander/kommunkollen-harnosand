<script setup lang="ts">
// Sammanträdesplanerna (#68) för redaktionen: organens planer så som webbsidan visar dem, med inställda och
// borttagna sammanträden, ändringar som versioner, och skillnaderna mot organets beslut om planen i protokollen.
// Skillnaderna visas inte publikt. Valt organ står i URL:en.
import { computed, inject, onMounted, ref, type Ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { EjInloggad, hamtaSammantradesplaner, type Jag, type Planskillnad, type Sammantradesplan } from '../../api'
import { datumTid, sammantradesdatum } from '../../format'

const STATUS = { planerat: 'Planerat', installt: 'Inställt', borttaget: 'Borttaget ur planen' } as const
const SKILLNAD: Record<Planskillnad['typ'], string> = {
  bara_sidan: 'Bara på webbsidan',
  bara_beslutet: 'Bara i beslutet',
  tid: 'Annan tid',
}

const route = useRoute()
const router = useRouter()
const utloggad = inject<() => void>('utloggad', () => {})
const jag = inject<Ref<Jag | null>>('jag', ref(null))
const arRedaktor = computed(() => jag.value?.roller.includes('redaktor') ?? false)

const planer = ref<Sammantradesplan[]>([])
const laddar = ref(true)
const fel = ref<string | null>(null)

const valtOrgan = computed<string>({
  get: () => (typeof route.query.organ === 'string' ? route.query.organ : ''),
  set: (v) => router.replace({ query: { ...route.query, organ: v || undefined } }),
})
const organ = computed(() => [...new Map(planer.value.map((p) => [p.organ.id, p.organ])).values()])
const visade = computed(() => planer.value.filter((p) => !valtOrgan.value || p.organ.id === valtOrgan.value))

onMounted(async () => {
  if (!arRedaktor.value) {
    laddar.value = false
    return
  }
  try {
    planer.value = await hamtaSammantradesplaner()
  } catch (e) {
    if (e instanceof EjInloggad) return utloggad()
    fel.value = e instanceof Error ? e.message : String(e)
  } finally {
    laddar.value = false
  }
})

const MANAD = new Intl.DateTimeFormat('sv-SE', { month: 'long', year: 'numeric', timeZone: 'UTC' })
function nar(datum: string | null, manad: string): string {
  return datum ? sammantradesdatum(datum) : MANAD.format(new Date(`${manad}-15T12:00:00Z`))
}
function tid(t: string | null): string {
  return t ? `kl. ${t.replace(':', '.')}` : '–'
}
</script>

<template>
  <header class="vyhuvud">
    <h1>Sammanträdesplaner</h1>
    <p class="ingress">
      Sammanträdesplanerna så som de står på kommunens webbsidor för organen. Ändringar i en plan sparas som
      versioner. Planen jämförs med organets beslut om sammanträdesplanen i protokollen, och skillnaderna visas här
      för redaktionen.
    </p>
  </header>
  <p v-if="!arRedaktor" class="saknas">Sammanträdesplanerna visas bara för redaktörer.</p>
  <template v-else>
    <p v-if="laddar">Hämtar sammanträdesplaner…</p>
    <p v-else-if="fel" class="fel" role="alert">{{ fel }}</p>
    <template v-else>
      <label class="filter">
        Organ
        <select v-model="valtOrgan" data-testid="organfilter">
          <option value="">Alla organ</option>
          <option v-for="o in organ" :key="o.id" :value="o.id">{{ o.namn }}</option>
        </select>
      </label>
      <p v-if="!planer.length" class="saknas">Inga sammanträdesplaner är inlästa än.</p>
      <section
        v-for="p in visade"
        :key="`${p.organ.id}-${p.ar}`"
        class="plan"
        data-testid="sammantradesplan"
        :data-organ="p.organ.id"
        :data-ar="p.ar"
        :aria-labelledby="`plan-${p.organ.id}-${p.ar}`"
      >
        <h2 :id="`plan-${p.organ.id}-${p.ar}`">{{ p.organ.namn }} {{ p.ar }}</h2>

        <p v-if="p.bara_beslut" class="bara-beslut" data-testid="bara-beslut">
          Ingen plan på webbsidan än. Sammanträdena kommer från organets beslut i protokollet och ersätts när
          kommunen publicerar tabellen.
        </p>
        <div class="jamforelse" data-testid="jamforelse">
          <template v-if="p.beslut.length">
            <p>
              Beslut om planen:
              <template v-for="(b, i) in p.beslut" :key="`${b.sammantrade_id}-${b.paragraf}`">
                <template v-if="i">, </template>
                <RouterLink :to="`/politik/sammantraden/${b.sammantrade_id}/paragraf/${b.paragraf}`">
                  {{ sammantradesdatum(b.datum) }} § {{ b.paragraf }} {{ b.rubrik }}
                </RouterLink>
              </template>
            </p>
            <p v-if="p.bara_beslut" class="anteckning">Inget att jämföra med förrän webbsidan har en plan.</p>
            <p v-else-if="p.skillnader === null" class="anteckning">Beslutet anger inte datumen, så planen kan inte jämföras.</p>
            <p v-else-if="!p.skillnader.length" class="lika" data-testid="inga-skillnader">
              <span aria-hidden="true">✓</span> Webbsidan stämmer med beslutet.
            </p>
            <ul v-else class="skillnader" data-testid="skillnader">
              <li v-for="s in p.skillnader" :key="s.datum" :data-datum="s.datum" :data-typ="s.typ">
                <span aria-hidden="true">!</span> <strong>{{ SKILLNAD[s.typ] }}:</strong> {{ sammantradesdatum(s.datum) }}
                <template v-if="s.typ === 'tid'">, {{ tid(s.sidan) }} på webbsidan och {{ tid(s.beslutet) }} i beslutet</template>
                <template v-else-if="s.typ === 'bara_beslutet' && s.sidan">
                  ({{ STATUS[s.sidan as keyof typeof STATUS].toLowerCase() }} på webbsidan)
                </template>
              </li>
            </ul>
          </template>
          <p v-else class="anteckning">Inget beslut om planen hittades i protokollen.</p>
        </div>

        <table class="tabell">
          <thead>
            <tr>
              <th scope="col">Datum</th>
              <th scope="col">Tid</th>
              <th scope="col">Status</th>
              <th scope="col">Källa</th>
              <th scope="col">Protokoll</th>
              <th scope="col">Ändringar</th>
            </tr>
          </thead>
          <tbody>
            <tr
              v-for="s in p.sammantraden"
              :key="s.id"
              :class="s.status"
              data-testid="planerat-sammantrade"
              :data-nyckel="s.nyckel"
              :data-status="s.status"
              :data-kalla="s.kalla"
            >
              <td class="datum">{{ nar(s.datum, s.manad) }}</td>
              <td>{{ tid(s.starttid) }}</td>
              <td>
                {{ STATUS[s.status] }}
                <span v-if="s.anmarkning" class="anmarkning" data-testid="anmarkning">
                  <span aria-hidden="true">!</span> Okänd text: ”{{ s.anmarkning }}”
                </span>
              </td>
              <td data-testid="kalla">
                <RouterLink
                  v-if="s.beslut"
                  :to="`/politik/sammantraden/${s.beslut.sammantrade_id}/paragraf/${s.beslut.paragraf}`"
                >
                  Beslut {{ s.beslut.datum ? sammantradesdatum(s.beslut.datum) : '' }} § {{ s.beslut.paragraf }}
                </RouterLink>
                <template v-else>Webbsidan</template>
              </td>
              <td>
                <RouterLink v-if="s.protokoll" :to="`/politik/sammantraden/${s.id}`">Protokoll</RouterLink>
                <span v-else class="anteckning">–</span>
              </td>
              <td>
                <details v-if="s.versioner.length > 1" data-testid="versioner">
                  <summary>{{ s.versioner.length - 1 }} {{ s.versioner.length === 2 ? 'ändring' : 'ändringar' }}</summary>
                  <ol>
                    <li v-for="v in s.versioner" :key="v.version">
                      {{ datumTid(v.hamtad) }}: {{ STATUS[v.status] }}, {{ tid(v.starttid) }},
                      {{ v.kalla === 'beslut' ? 'enligt beslutet' : 'enligt webbsidan' }}
                      <span v-if="v.kalltext" class="anteckning">(”{{ v.kalltext }}”)</span>
                    </li>
                  </ol>
                </details>
                <span v-else class="anteckning">–</span>
              </td>
            </tr>
          </tbody>
        </table>
        <p v-if="p.url" class="kallrad">
          Källa: <a :href="p.url" rel="noopener">{{ p.organ.namn }} på harnosand.se</a>
        </p>
      </section>
    </template>
  </template>
</template>

<style scoped>
.vyhuvud {
  margin-bottom: 24px;
}
.ingress {
  color: var(--ink-secondary);
  margin: 0;
  max-width: 70ch;
}
.filter {
  display: inline-flex;
  gap: 8px;
  align-items: center;
  font-size: 13px;
  margin-bottom: 16px;
}
.plan {
  margin-bottom: 32px;
}
.plan h2 {
  font-size: 18px;
  margin: 0 0 8px;
}
.jamforelse {
  font-size: 14px;
  margin-bottom: 12px;
}
.jamforelse p {
  margin: 0 0 4px;
}
.skillnader {
  margin: 4px 0 0;
  padding-left: 0;
  list-style: none;
}
.skillnader li > span[aria-hidden='true'],
.anmarkning > span[aria-hidden='true'] {
  color: var(--status-warning);
  font-weight: 700;
}
.lika span {
  color: var(--status-good);
}
.anteckning,
.kallrad {
  color: var(--ink-muted);
  font-size: 12px;
}
.kallrad {
  margin: 8px 0 0;
}
.bara-beslut {
  font-size: 14px;
  color: var(--ink-secondary);
  margin: 0 0 8px;
}
.anmarkning {
  display: block;
  font-size: 12px;
  color: var(--ink-secondary);
}
.tabell {
  border-collapse: collapse;
  width: 100%;
  font-size: 13px;
}
.tabell th,
.tabell td {
  text-align: left;
  padding: 6px 8px;
  border-bottom: 1px solid var(--line);
  vertical-align: top;
}
.tabell thead th {
  color: var(--ink-secondary);
  font-weight: 600;
}
.tabell td.datum {
  white-space: nowrap;
}
tr.installt td.datum,
tr.borttaget td.datum {
  text-decoration: line-through;
  color: var(--ink-muted);
}
details ol {
  margin: 4px 0 0;
  padding-left: 18px;
}
.saknas {
  color: var(--ink-secondary);
}
.fel {
  color: var(--status-critical);
}
@media (max-width: 640px) {
  .tabell {
    display: block;
    overflow-x: auto;
  }
}
</style>
