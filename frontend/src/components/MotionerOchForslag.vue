<script setup lang="ts">
// Motioner och medborgarförslag (#45): väckta och besvarade per år, utfall per parti, och varje
// motion och förslag med ledtid. Över ett år markeras sakligt (kommunallagen 5 kap. 35 §).
import { computed, inject, ref, type Ref } from 'vue'
import type { Forlopp, Jag, Motionsstatistik } from '../api'
import { parti, sammantradesdatum, tal } from '../format'
import Motionarformular from './Motionarformular.vue'
import Periodmarkering from './Periodmarkering.vue'
import Rattelsemarkering from './Rattelsemarkering.vue'

const props = defineProps<{ m: Motionsstatistik }>()

// Rätta motionärer (#78): redaktörer och utgivare kan skriva en rättelse, och redaktören har en arbetslista.
const jag = inject<Ref<Jag | null>>('jag', ref(null))
const utloggad = inject<() => void>('utloggad', () => {})
const arRedaktor = computed(() => jag.value?.roller.includes('redaktor') ?? false)
const kanRatta = computed(() => arRedaktor.value || (jag.value?.roller.includes('utgivare') ?? false))
const utanMotionar = ref(false)
const rattar = ref<number | null>(null)
const sparad = ref<{ arende: number; id: number } | null>(null)
const motioner = computed(() =>
  utanMotionar.value ? props.m.motioner.lista.filter((f) => !f.motionarer.length) : props.m.motioner.lista,
)
function sparat(arende: number, id: number) {
  rattar.value = null
  sparad.value = { arende, id }
}

const utfallsnamn = computed(() => Object.fromEntries(props.m.utfall.map((u) => [u.id, u.namn])) as Record<string, string>)
const summa = computed(() =>
  props.m.motioner.per_ar.reduce(
    (s, r) => ({ vackta: s.vackta + r.vackta, besvarade: s.besvarade + r.besvarade }),
    { vackta: 0, besvarade: 0 },
  ),
)
const lank = (b: { sammantrade: { id: number }; paragraf: number }) =>
  `/politik/sammantraden/${b.sammantrade.id}/paragraf/${b.paragraf}`
const ledtid = (f: Forlopp) => (f.ledtid_dagar === null ? null : `${tal(f.ledtid_dagar)} dagar`)
const partinamn = (p: string) => (p === 'okant' ? 'Parti anges inte' : parti(p))
</script>

<template>
  <section class="kort" aria-labelledby="motioner-rubrik" data-testid="motioner">
    <h2 id="motioner-rubrik">Motioner</h2>
    <p class="forklaring">
      En motion väcks när kommunfullmäktige överlämnar den till kommunstyrelsen för beredning, och besvaras när
      fullmäktige fattar beslut i sak. Den ska enligt kommunallagen beredas inom ett år.
    </p>
    <div class="nyckeltal">
      <div class="tal"><span class="varde" data-testid="vackta">{{ tal(summa.vackta) }}</span><span class="etikett">Väckta</span></div>
      <div class="tal"><span class="varde" data-testid="besvarade">{{ tal(summa.besvarade) }}</span><span class="etikett">Besvarade</span></div>
      <div v-for="u in m.utfall" :key="u.id" class="tal">
        <span class="varde">{{ tal(m.motioner.per_ar.reduce((s, r) => s + r.utfall[u.id], 0)) }}</span>
        <span class="etikett">{{ u.namn }}</span>
      </div>
    </div>

    <div class="rulla">
      <table class="tabell" data-testid="motioner-per-ar">
        <caption>Per år</caption>
        <thead>
          <tr>
            <th scope="col">År</th>
            <th scope="col" class="num">Väckta</th>
            <th scope="col" class="num">Besvarade</th>
            <th v-for="u in m.utfall" :key="u.id" scope="col" class="num">{{ u.namn }}</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="r in m.motioner.per_ar" :key="r.ar">
            <th scope="row">{{ r.ar }}</th>
            <td class="num">{{ tal(r.vackta) }}</td>
            <td class="num">{{ tal(r.besvarade) }}</td>
            <td v-for="u in m.utfall" :key="u.id" class="num">{{ tal(r.utfall[u.id]) }}</td>
          </tr>
        </tbody>
      </table>
    </div>

    <div v-if="m.motioner.per_parti.length" class="rulla">
      <table class="tabell" data-testid="motioner-per-parti">
        <caption>Per motionärernas parti</caption>
        <thead>
          <tr>
            <th scope="col">Parti</th>
            <th scope="col" class="num">Väckta</th>
            <th scope="col" class="num">Besvarade</th>
            <th v-for="u in m.utfall" :key="u.id" scope="col" class="num">{{ u.namn }}</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="r in m.motioner.per_parti" :key="r.parti" :data-parti="r.parti">
            <th scope="row">{{ partinamn(r.parti) }}</th>
            <td class="num">{{ tal(r.vackta) }}</td>
            <td class="num">{{ tal(r.besvarade) }}</td>
            <td v-for="u in m.utfall" :key="u.id" class="num">{{ tal(r.utfall[u.id]) }}</td>
          </tr>
        </tbody>
      </table>
      <p class="kallrad">En motion med motionärer från flera partier räknas för varje parti.</p>
    </div>

    <label v-if="arRedaktor && m.motioner.lista.length" class="filter">
      <input v-model="utanMotionar" type="checkbox" data-testid="utan-motionar" /> Motioner utan motionär
    </label>
    <p v-if="!m.motioner.lista.length" class="saknas">Inga motioner för perioden.</p>
    <div v-else class="rulla">
      <table class="tabell lista" data-testid="motionslista">
        <caption>Motionerna</caption>
        <thead>
          <tr>
            <th scope="col">Motion</th>
            <th scope="col">Motionär</th>
            <th scope="col">Väckt</th>
            <th scope="col">Besvarad</th>
            <th scope="col">Utfall</th>
            <th scope="col" class="num">Ledtid</th>
          </tr>
        </thead>
        <tbody>
          <template v-for="f in motioner" :key="f.arende_id">
          <tr data-testid="motion" :data-arende="f.arende_id">
            <td class="rubrik">
              <RouterLink :to="`/politik/arenden/${f.arende_id}`">{{ f.rubrik }}</RouterLink>
              <span v-if="f.aterremisser" class="not">Återremitterad {{ f.aterremisser }} gång{{ f.aterremisser > 1 ? 'er' : '' }}</span>
              <span v-if="f.bordlaggningar" class="not">Bordlagd {{ f.bordlaggningar }} gång{{ f.bordlaggningar > 1 ? 'er' : '' }}</span>
              <span v-if="f.behandlingar.some((b) => b.osaker)" class="not forslag" title="Kopplad på rubriken, inte på diarienummer">
                ≈ Innehåller föreslagen koppling
              </span>
            </td>
            <td data-testid="motionarer">
              <template v-if="f.motionarer.length">
                <span v-for="(p, i) in f.motionarer" :key="i" class="person">
                  <RouterLink v-if="p.person_id && p.namn" :to="`/politik/ledamoter/${p.person_id}`">{{ p.namn }}</RouterLink>
                  <template v-else>{{ p.namn ?? 'Partiet' }}</template><template v-if="p.parti"> ({{ p.parti }})</template><Periodmarkering v-if="p.partitillhorighet" :period="p.partitillhorighet" />
                </span>
              </template>
              <span v-else class="saknas">Uppgift saknas</span>
              <Rattelsemarkering v-if="f.rattelser?.motionarer" :rattelse="f.rattelser.motionarer" falt="motionarer" />
              <button v-if="kanRatta && rattar !== f.arende_id" type="button" class="lank" data-testid="ratta-motionarer" @click="rattar = f.arende_id">
                Rätta
              </button>
              <span v-if="sparad?.arende === f.arende_id" class="not" role="status" data-testid="motionarer-sparade">
                Sparat som utkast. Publiceras efter granskning.
              </span>
            </td>
            <td>
              <RouterLink v-if="f.vackt" :to="lank({ sammantrade: { id: f.vackt.sammantrade_id }, paragraf: f.vackt.paragraf })">
                {{ sammantradesdatum(f.vackt.datum) }}
              </RouterLink>
              <span v-if="f.vackt?.osaker" class="not forslag" title="Kopplad på rubriken i samlingspunkten">≈ Förslag</span>
              <span v-if="!f.vackt" class="saknas">Uppgift saknas</span>
            </td>
            <td>
              <RouterLink v-if="f.besvarad" :to="lank(f.besvarad)">{{ sammantradesdatum(f.besvarad.sammantrade.datum) }}</RouterLink>
              <span v-else>Obesvarad</span>
            </td>
            <td>{{ f.utfall ? utfallsnamn[f.utfall] : '' }}</td>
            <td class="num">
              {{ ledtid(f) }}
              <span v-if="f.over_ett_ar" class="over" data-testid="over-ett-ar">{{ f.besvarad ? 'Mer än ett år' : 'Obesvarad mer än ett år' }}</span>
            </td>
          </tr>
          <tr v-if="rattar === f.arende_id" class="rattelserad">
            <td colspan="6">
              <Motionarformular
                :rubrik="f.rubrik"
                :motionarer="f.motionarer"
                :mal="f.rattelsemal"
                @sparad="(id) => sparat(f.arende_id, id)"
                @avbryt="rattar = null"
                @utloggad="utloggad"
              />
            </td>
          </tr>
          </template>
        </tbody>
      </table>
      <p v-if="m.motioner.utan_vackt" class="kallrad">
        För {{ m.motioner.utan_vackt }} motioner står det inte i protokollen när de väcktes, ofta för att det skedde före
        de protokoll som finns här.
      </p>
    </div>
  </section>

  <section class="kort" aria-labelledby="forslag-rubrik" data-testid="medborgarforslag">
    <h2 id="forslag-rubrik">Medborgarförslag (e-förslag)</h2>
    <p class="forklaring">
      I Härnösand lämnas medborgarförslag som e-förslag och besvaras av den nämnd som ansvarar för frågan. När förslaget
      lämnades står inte i protokollen, så tiden räknas från den första behandlingen.
    </p>
    <p v-if="!m.medborgarforslag.lista.length" class="saknas">Inga medborgarförslag för perioden.</p>
    <div v-else class="rulla">
      <table class="tabell lista" data-testid="forslagslista">
        <thead>
          <tr>
            <th scope="col">Förslag</th>
            <th scope="col">Väckt</th>
            <th scope="col">Besvarad</th>
            <th scope="col">Organ</th>
            <th scope="col">Utfall</th>
            <th scope="col">Beslut</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="f in m.medborgarforslag.lista" :key="f.arende_id" data-testid="forslag">
            <td class="rubrik">
              <RouterLink :to="`/politik/arenden/${f.arende_id}`">{{ f.rubrik }}</RouterLink>
              <span v-if="f.aterremisser" class="not">Återremitterat {{ f.aterremisser }} gång{{ f.aterremisser > 1 ? 'er' : '' }}</span>
            </td>
            <td><span class="saknas">Uppgift saknas</span></td>
            <td>
              <RouterLink v-if="f.besvarad" :to="lank(f.besvarad)">{{ sammantradesdatum(f.besvarad.sammantrade.datum) }}</RouterLink>
              <span v-else>Obesvarat</span>
              <span v-if="f.over_ett_ar" class="over">Mer än ett år efter första behandlingen</span>
            </td>
            <td>{{ (f.besvarad ?? f.forsta_behandling).sammantrade.organ.namn }}</td>
            <td>{{ f.utfall ? utfallsnamn[f.utfall] : '' }}</td>
            <td class="beslut">{{ f.besvarad?.beslut }}</td>
          </tr>
        </tbody>
      </table>
    </div>
  </section>
</template>

<style scoped>
.filter {
  display: block;
  font-size: 13px;
  color: var(--ink-secondary);
  margin: 12px 0 4px;
}
.lank {
  font: inherit;
  font-size: 12px;
  border: none;
  background: none;
  color: var(--accent);
  cursor: pointer;
  padding: 0;
  margin-left: 6px;
}
.rattelserad td {
  background: var(--surface-raised);
}
.kort {
  background: var(--surface);
  border: 1px solid var(--line);
  border-radius: var(--radius);
  padding: 16px 24px;
  margin-bottom: 16px;
}
.kort h2 {
  font-size: 15px;
  margin: 0 0 8px;
}
.forklaring {
  font-size: 13px;
  color: var(--ink-secondary);
  max-width: 70ch;
  margin: 0 0 12px;
}
.nyckeltal {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(110px, 1fr));
  gap: 8px;
  margin-bottom: 16px;
}
.tal {
  border: 1px solid var(--line);
  border-radius: var(--radius);
  padding: 8px 12px;
  display: grid;
}
.tal .varde {
  font-size: 20px;
  font-weight: 600;
  font-variant-numeric: tabular-nums;
}
.tal .etikett {
  font-size: 12px;
  color: var(--ink-secondary);
}
.rulla {
  overflow-x: auto;
  margin-bottom: 16px;
}
.tabell {
  border-collapse: collapse;
  width: 100%;
  font-size: 13px;
}
.tabell caption {
  text-align: left;
  font-weight: 600;
  padding: 4px 0;
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
  white-space: nowrap;
}
.tabell .num {
  text-align: right;
  font-variant-numeric: tabular-nums;
  white-space: nowrap;
}
.lista .rubrik {
  min-width: 240px;
}
.lista .beslut {
  min-width: 260px;
  white-space: pre-line;
  color: var(--ink-secondary);
}
.person {
  display: block;
  white-space: nowrap;
}
.not,
.over {
  display: block;
  font-size: 12px;
  color: var(--ink-secondary);
}
.over {
  display: inline-block;
  margin-top: 2px;
  padding: 0 6px;
  border: 1px solid var(--line-strong);
  border-radius: var(--radius);
}
.forslag {
  font-style: italic;
}
.saknas {
  color: var(--ink-muted);
  font-style: italic;
}
.kallrad {
  font-size: 12px;
  color: var(--ink-muted);
  margin: 8px 0 0;
}
a {
  color: var(--accent);
}
</style>
