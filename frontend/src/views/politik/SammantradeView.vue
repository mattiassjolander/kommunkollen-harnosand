<script setup lang="ts">
import { computed, inject, ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import { EjInloggad, hamtaSammantrade, Saknas, type Person, type Sammantrade } from '../../api'
import { paragraftext, parti, sammantradesdatum } from '../../format'
import Partimarkering from '../../components/Partimarkering.vue'
import Protokollkalla from '../../components/Protokollkalla.vue'
import Tolkningsmarkering from '../../components/Tolkningsmarkering.vue'

const route = useRoute()
const utloggad = inject<() => void>('utloggad', () => {})

const s = ref<Sammantrade | null>(null)
const laddar = ref(true)
const fel = ref<string | null>(null)

async function ladda() {
  laddar.value = true
  fel.value = null
  try {
    s.value = await hamtaSammantrade(String(route.params.id))
  } catch (e) {
    if (e instanceof EjInloggad) return utloggad()
    fel.value = e instanceof Saknas ? 'Sammanträdet finns inte.' : e instanceof Error ? e.message : String(e)
  } finally {
    laddar.value = false
  }
}
watch(() => route.params.id, ladda, { immediate: true })

const GRUPPER: { kategori: Person['kategori']; titel: string }[] = [
  { kategori: 'beslutande', titel: 'Beslutande' },
  { kategori: 'ej_tjanstgorande', titel: 'Närvarande ersättare, ej tjänstgörande' },
  { kategori: 'franvarande', titel: 'Frånvarande' },
  { kategori: 'ovrig', titel: 'Övriga närvarande' },
]
const narvaro = computed(() =>
  GRUPPER.map((g) => ({ ...g, personer: s.value?.narvaro.filter((p) => p.kategori === g.kategori) ?? [] })).filter(
    (g) => g.personer.length,
  ),
)

function anteckning(p: Person): string {
  const delar: string[] = []
  if (p.tjanstgor_for) delar.push(`Tjänstgör för ${p.tjanstgor_for.namn} (${parti(p.tjanstgor_for.parti)})`)
  if (p.paragrafer) delar.push(`Beslutande vid ${paragraftext(p.paragrafer)}`)
  if (p.jav.length) delar.push(`Jäv ${paragraftext(p.jav)}`)
  return delar.join(' · ')
}
const tid = computed(() =>
  s.value?.starttid ? `kl. ${s.value.starttid}${s.value.sluttid ? `–${s.value.sluttid}` : ''}` : null,
)
</script>

<template>
  <nav class="brodsmulor" aria-label="Brödsmulor">
    <RouterLink to="/politik">Politik och beslut</RouterLink>
    <span aria-hidden="true">›</span>
    <span>{{ s ? `${s.organ.namn} ${s.datum ?? ''}` : 'Sammanträde' }}</span>
  </nav>

  <p v-if="laddar">Hämtar uppgifter…</p>
  <p v-else-if="fel" class="fel">{{ fel }}</p>

  <template v-else-if="s">
    <header class="vyhuvud">
      <h1>{{ s.organ.namn }}</h1>
      <p class="ingress" data-testid="sammantradesinfo">
        <span class="forsta-versal">{{ sammantradesdatum(s.datum) }}</span>
        <template v-if="tid">, {{ tid }}</template>
        <template v-if="s.plats"> · {{ s.plats }}</template>
        <template v-if="s.paragrafer">
          · {{ s.paragrafer[0] === s.paragrafer[1] ? `§ ${s.paragrafer[0]}` : `§§ ${s.paragrafer[0]}–${s.paragrafer[1]}` }}
        </template>
      </p>
      <p class="markering"><Tolkningsmarkering :ej-tolkad="s.tolkning === 'ej_tolkad'" /></p>
      <Protokollkalla :protokoll="s.protokoll" />
    </header>

    <section v-if="s.avvikelser.length" class="kort avvikelser" data-testid="avvikelser" aria-labelledby="avv-rubrik">
      <h2 id="avv-rubrik">Avvikelser vid tolkningen</h2>
      <p class="ingress">Det här stämde inte med det förväntade när protokollet lästes. Kontrollera mot protokollet.</p>
      <ul>
        <li v-for="a in s.avvikelser" :key="a">{{ a }}</li>
      </ul>
    </section>

    <section class="kort" aria-labelledby="beh-rubrik">
      <h2 id="beh-rubrik">Behandlingar</h2>
      <p v-if="!s.behandlingar.length" class="ingress">Inga behandlingar kunde läsas ur protokollet.</p>
      <ol class="behandlingar" data-testid="behandlingar">
        <li v-for="b in s.behandlingar" :key="b.paragraf" data-testid="behandling" :data-paragraf="b.paragraf">
          <RouterLink :to="`/politik/sammantraden/${s.id}/paragraf/${b.paragraf}`" class="paragraf">
            <span class="nr">§ {{ b.paragraf }}</span>
            <span class="rubrik">{{ b.rubrik || 'Rubrik saknas' }}</span>
          </RouterLink>
          <span v-if="b.diarienummer.length" class="dnr">{{ b.diarienummer.join(', ') }}</span>
          <span v-if="b.antal_voteringar" class="etikett" data-testid="har-votering">
            {{ b.antal_voteringar > 1 ? `${b.antal_voteringar} voteringar` : 'Votering' }}
          </span>
          <span v-if="b.antal_reservationer" class="etikett" data-testid="har-reservation">Reservation</span>
          <p v-if="b.beslut" class="beslut">{{ b.beslut }}</p>
        </li>
      </ol>
    </section>

    <section class="kort" aria-labelledby="narv-rubrik" data-testid="narvaro">
      <h2 id="narv-rubrik">Närvaro</h2>
      <p class="ingress">Som protokollet anger det, med partitillhörighet vid det här sammanträdet.</p>
      <p v-if="!narvaro.length" class="ingress">Närvarolistan kunde inte läsas ur protokollet.</p>
      <div v-for="g in narvaro" :key="g.kategori" class="grupp">
        <h3>{{ g.titel }} <span class="antal">({{ g.personer.length }})</span></h3>
        <table class="tabell" :data-testid="`narvaro-${g.kategori}`">
          <thead>
            <tr>
              <th scope="col">Namn</th>
              <th scope="col">Parti</th>
              <th scope="col">Roll</th>
              <th scope="col">Anteckning</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="p in g.personer" :key="p.namn + p.roll" data-testid="person">
              <th scope="row">
                <RouterLink v-if="p.ledamot_id" :to="`/politik/ledamoter/${p.ledamot_id}`">{{ p.namn }}</RouterLink>
                <template v-else>{{ p.namn }}</template>
              </th>
              <td><Partimarkering :parti="p.parti" /></td>
              <td>{{ p.roll ?? '–' }}</td>
              <td>{{ anteckning(p) }}</td>
            </tr>
          </tbody>
        </table>
      </div>
    </section>
  </template>
</template>

<style scoped>
.brodsmulor {
  display: flex;
  gap: 8px;
  font-size: 13px;
  color: var(--ink-muted);
  margin-bottom: 12px;
}
.brodsmulor a {
  color: var(--accent);
}
.vyhuvud {
  margin-bottom: 24px;
}
.ingress {
  color: var(--ink-secondary);
  margin: 0;
  max-width: 70ch;
}
.forsta-versal {
  display: inline-block;
}
.forsta-versal::first-letter {
  text-transform: uppercase;
}
.markering {
  margin: 12px 0 0;
}
.kort {
  background: var(--surface);
  border: 1px solid var(--line);
  border-radius: var(--radius);
  padding: 24px;
  margin-bottom: 24px;
  overflow-x: auto;
}
.kort h2 {
  margin-bottom: 12px;
}
.avvikelser ul {
  margin: 12px 0 0;
  padding-left: 20px;
  font-size: 13px;
}
.behandlingar {
  list-style: none;
  margin: 0;
  padding: 0;
}
.behandlingar li {
  padding: 12px 0;
  border-bottom: 1px solid var(--line);
}
.paragraf {
  display: inline-flex;
  gap: 12px;
  font-weight: 600;
  color: var(--ink);
  text-decoration: none;
}
.paragraf:hover .rubrik {
  color: var(--accent);
  text-decoration: underline;
}
.nr {
  min-width: 48px;
  font-variant-numeric: tabular-nums;
  color: var(--ink-secondary);
}
.dnr {
  margin-left: 12px;
  font-size: 12px;
  color: var(--ink-muted);
}
.etikett {
  margin-left: 8px;
  padding: 1px 6px;
  border: 1px solid var(--line-strong);
  border-radius: var(--radius);
  font-size: 11px;
  color: var(--ink-secondary);
  white-space: nowrap;
}
.beslut {
  margin: 6px 0 0 60px;
  font-size: 13px;
  color: var(--ink-secondary);
  white-space: pre-line;
  max-width: 80ch;
}
.grupp + .grupp {
  margin-top: 20px;
}
.grupp h3 {
  font-size: 14px;
  margin: 16px 0 8px;
}
.antal {
  color: var(--ink-muted);
  font-weight: 400;
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
}
.tabell tbody th {
  font-weight: 600;
}
.saknas {
  color: var(--ink-muted);
  font-style: italic;
}
.fel {
  color: var(--status-critical);
}
</style>
