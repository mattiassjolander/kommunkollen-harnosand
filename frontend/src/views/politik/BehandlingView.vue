<script setup lang="ts">
import { computed, inject, ref, watch, type Ref } from 'vue'
import { useRoute } from 'vue-router'
import {
  BEHANDLINGSTYPER, EjInloggad, hamtaBehandling, Saknas, type Behandling, type Jag, type Votering } from '../../api'
import { tidsintervall, namnOchParti, rosttext, sammantradesdatum } from '../../format'
import Harledningsmarkering from '../../components/Harledningsmarkering.vue'
import Kallelsemarkering from '../../components/Kallelsemarkering.vue'
import Periodmarkering from '../../components/Periodmarkering.vue'
import Partimarkering from '../../components/Partimarkering.vue'
import Protokollkalla from '../../components/Protokollkalla.vue'
import Rattelseformular from '../../components/Rattelseformular.vue'
import Rattelsemarkering from '../../components/Rattelsemarkering.vue'
import Tolkningsmarkering from '../../components/Tolkningsmarkering.vue'

const route = useRoute()
const utloggad = inject<() => void>('utloggad', () => {})
const jag = inject<Ref<Jag | null>>('jag', ref(null))
const arRedaktor = computed(() => jag.value?.roller.includes('redaktor') ?? false)

const b = ref<Behandling | null>(null)
const laddar = ref(true)
const fel = ref<string | null>(null)

async function ladda() {
  laddar.value = true
  fel.value = null
  try {
    b.value = await hamtaBehandling(String(route.params.id), String(route.params.paragraf))
  } catch (e) {
    if (e instanceof EjInloggad) return utloggad()
    fel.value = e instanceof Saknas ? 'Paragrafen finns inte i sammanträdet.' : e instanceof Error ? e.message : String(e)
  } finally {
    laddar.value = false
  }
}
watch(() => [route.params.id, route.params.paragraf], ladda, { immediate: true })

const sammantradeslank = computed(() => `/politik/sammantraden/${route.params.id}`)
const lank = (p: number) => `${sammantradeslank.value}/paragraf/${p}`

const ANTAL = ['ja', 'nej', 'avstar', 'franvarande'] as const

/** Protokollets text och voteringslistan anger olika siffror. */
function avviker(v: Votering) {
  return ANTAL.some((k) => v.angivet[k] !== null && v.angivet[k] !== v.lista[k])
}
function angivet(v: Votering) {
  return ANTAL.filter((k) => v.angivet[k] !== null)
    .map((k) => `${v.angivet[k]} ${rosttext(k).toLowerCase()}`)
    .join(', ')
}
function vinnande(v: Votering) {
  if (v.vinnare === 'ja') return v.ja_forslag ?? 'ja-förslaget'
  if (v.vinnare === 'nej') return v.nej_forslag ?? 'nej-förslaget'
  return null
}
const voteringsrubrik = (v: Votering, antal: number) => (antal > 1 ? `Votering ${v.nummer}` : 'Votering')
</script>

<template>
  <nav class="brodsmulor" aria-label="Brödsmulor">
    <RouterLink to="/politik">Politik och beslut</RouterLink>
    <span aria-hidden="true">›</span>
    <RouterLink :to="sammantradeslank">
      {{ b ? `${b.sammantrade.organ.namn} ${b.sammantrade.datum ?? ''}` : 'Sammanträde' }}
    </RouterLink>
    <span aria-hidden="true">›</span>
    <span>§ {{ route.params.paragraf }}</span>
  </nav>

  <p v-if="laddar">Hämtar uppgifter…</p>
  <p v-else-if="fel" class="fel">{{ fel }}</p>

  <template v-else-if="b">
    <header class="vyhuvud">
      <p class="overrubrik">
        § {{ b.paragraf }} · {{ b.sammantrade.organ.namn }},
        <span class="forsta-versal">{{ sammantradesdatum(b.sammantrade.datum) }}</span>
      </p>
      <h1>{{ b.rubrik || 'Rubrik saknas' }}</h1>
      <p v-if="b.rubrik_ur_arendelistan" class="ingress" data-testid="rubrik-ur-arendelistan">
        Rubriken hämtad ur ärendelistan. Den hittades inte i paragrafen.
      </p>
      <p v-if="b.rattelser?.rubrik" class="rattelserad">
        <Rattelsemarkering :rattelse="b.rattelser.rubrik" falt="rubrik" />
      </p>
      <p v-if="b.diarienummer.length || b.rattelser?.diarienummer" class="ingress" data-testid="diarienummer">
        Diarienummer {{ b.diarienummer.join(', ') || 'saknas' }}
        <Kallelsemarkering v-if="b.diarienummer_kallelse" :kalla="b.diarienummer_kallelse" />
        <Rattelsemarkering v-if="b.rattelser?.diarienummer" :rattelse="b.rattelser.diarienummer" falt="diarienummer" />
      </p>
      <p class="ingress" data-testid="typ">
        Typ: {{ BEHANDLINGSTYPER.find((t) => t.id === b?.typ)?.namn ?? 'kunde inte klassas' }}
        <Rattelsemarkering v-if="b.rattelser?.typ" :rattelse="b.rattelser.typ" falt="typ" />
      </p>
      <p v-if="b.sittning" class="ingress" data-testid="sittning">
        <template v-if="b.sittning.delegation">Beslut av {{ b.sittning.delegation }} på delegation. </template>
        Sittning {{ b.sittning.nummer }}<template v-if="tidsintervall(b.sittning.starttid, b.sittning.sluttid)"
          >, {{ tidsintervall(b.sittning.starttid, b.sittning.sluttid) }}</template
        ><template v-if="b.sittning.plats"> · {{ b.sittning.plats }}</template>
      </p>
      <p class="markering"><Tolkningsmarkering :ocr="b.sammantrade.ocr" /></p>
      <Protokollkalla :protokoll="b.sammantrade.protokoll" :paragraf="b.paragraf" />
    </header>

    <section v-if="b.paragraftext" class="kort" aria-labelledby="paragraftext-rubrik">
      <h2 id="paragraftext-rubrik">I paragrafen</h2>
      <p class="beslut" data-testid="paragraftext">{{ b.paragraftext }}</p>
    </section>

    <section class="kort" aria-labelledby="beslut-rubrik">
      <h2 id="beslut-rubrik">Beslut</h2>
      <p v-if="b.beslut" class="beslut" data-testid="beslut">{{ b.beslut }}</p>
      <p v-else class="saknas" data-testid="beslut">Protokollet anger inget beslut för paragrafen.</p>
      <p v-if="b.rattelser?.beslut" class="rattelserad">
        <Rattelsemarkering :rattelse="b.rattelser.beslut" falt="beslut" />
      </p>
    </section>

    <section v-if="b.arende" class="kort" aria-labelledby="arende-rubrik" data-testid="arende">
      <h2 id="arende-rubrik">Ärende</h2>
      <p v-if="b.arende.antal_behandlingar > 1" class="arendetext">
        Behandlingen ingår i ett ärende med {{ b.arende.antal_behandlingar }} behandlingar.
      </p>
      <p v-else class="arendetext">Ingen annan behandling är kopplad till ärendet än.</p>
      <RouterLink :to="`/politik/arenden/${b.arende.id}`" data-testid="arendelank">Ärendets väg ›</RouterLink>
    </section>

    <section
      v-if="b.styrande_dokument?.length"
      class="kort"
      aria-labelledby="styrdok-rubrik"
      data-testid="faststallda-dokument"
    >
      <h2 id="styrdok-rubrik">Styrande dokument</h2>
      <p class="arendetext">Fastställde enligt dokumentinformationen (samma organ, datum och diarienummer):</p>
      <ul>
        <li v-for="s in b.styrande_dokument" :key="s.id">
          <RouterLink :to="`/politik/styrande-dokument/${s.id}`">{{ s.titel }}</RouterLink>
        </li>
      </ul>
    </section>

    <section v-if="b.yrkanden.length" class="kort" aria-labelledby="yrk-rubrik" data-testid="yrkanden">
      <h2 id="yrk-rubrik">Yrkanden</h2>
      <ul class="yrkanden">
        <li v-for="(y, i) in b.yrkanden" :key="i" data-testid="yrkande">
          <p class="yrkandetext">{{ y.text }}</p>
          <p v-if="y.personer.length" class="anteckning">
            <template v-for="(p, j) in y.personer" :key="p.namn">
              <template v-if="j">, </template>
              <RouterLink v-if="p.ledamot_id" :to="`/politik/ledamoter/${p.ledamot_id}`">{{ p.namn }}</RouterLink>
              <template v-else>{{ p.namn }}</template>
              {{ ' ' }}<Partimarkering :parti="p.parti" /><Periodmarkering v-if="p.partitillhorighet" :period="p.partitillhorighet" />
            </template>
          </p>
        </li>
      </ul>
      <template v-if="b.propositionsordning">
        <h3>Propositionsordning</h3>
        <p class="lopande" data-testid="propositionsordning">{{ b.propositionsordning }}</p>
      </template>
    </section>

    <section
      v-for="v in b.voteringar"
      :id="`votering-${v.nummer}`"
      :key="v.nummer"
      class="kort"
      :aria-labelledby="`vot-rubrik-${v.nummer}`"
      data-testid="votering"
      :data-nummer="v.nummer"
    >
      <h2 :id="`vot-rubrik-${v.nummer}`">
        <a :href="`#votering-${v.nummer}`" class="ankare">{{ voteringsrubrik(v, b.voteringar.length) }}</a>
      </h2>
      <dl class="forslag">
        <dt>Ja</dt>
        <dd data-testid="ja-forslag">{{ v.ja_forslag ?? 'Anges inte i protokollet' }}</dd>
        <dt>Nej</dt>
        <dd data-testid="nej-forslag">{{ v.nej_forslag ?? 'Anges inte i protokollet' }}</dd>
      </dl>

      <p class="utfall" data-testid="utfall">
        <span class="tal">{{ v.lista.ja }}</span> ja, <span class="tal">{{ v.lista.nej }}</span> nej,
        <span class="tal">{{ v.lista.avstar }}</span> avstår<template v-if="v.lista.franvarande">,
          <span class="tal">{{ v.lista.franvarande }}</span> frånvarande</template>
        <span class="anteckning"> enligt voteringslistan</span>
      </p>
      <p v-if="avviker(v)" class="avvikelse" data-testid="avvikelse">
        Protokollets text anger {{ angivet(v) }}. Listan visas som den står i protokollet.
      </p>
      <p v-if="vinnande(v)" data-testid="vinnare">
        <strong>Bifölls:</strong> {{ vinnande(v) }} ({{ v.vinnare }})
      </p>
      <p v-else-if="v.resultat" data-testid="vinnare">
        <strong>Ordföranden konstaterar</strong> att {{ v.resultat }}.
      </p>

      <h3>Per parti</h3>
      <table class="tabell" data-testid="per-parti">
        <thead>
          <tr>
            <th scope="col">Parti</th>
            <th scope="col" class="hoger">Ja</th>
            <th scope="col" class="hoger">Nej</th>
            <th scope="col" class="hoger">Avstår</th>
            <th scope="col" class="hoger">Frånvarande</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="p in v.per_parti" :key="p.parti ?? ''" data-testid="partirad" :data-parti="p.parti ?? ''">
            <th scope="row"><Partimarkering :parti="p.parti" /></th>
            <td class="tal hoger" data-testid="ja">{{ p.ja }}</td>
            <td class="tal hoger" data-testid="nej">{{ p.nej }}</td>
            <td class="tal hoger" data-testid="avstar">{{ p.avstar }}</td>
            <td class="tal hoger" data-testid="franvarande">{{ p.franvarande }}</td>
          </tr>
        </tbody>
      </table>

      <details class="ledamoter" data-testid="per-ledamot">
        <summary>Röster per ledamot ({{ v.roster.length }})</summary>
        <table class="tabell">
          <thead>
            <tr>
              <th scope="col">Ledamot</th>
              <th scope="col">Parti</th>
              <th scope="col">Röst</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="(r, i) in v.roster" :key="i" data-testid="rost" :data-rost="r.rost">
              <th scope="row">
                <RouterLink v-if="r.ledamot_id" :to="`/politik/ledamoter/${r.ledamot_id}`">{{ r.namn }}</RouterLink>
                <template v-else>{{ r.namn ?? 'Tom stol' }}</template>
                <span v-if="r.ersatt" class="anteckning">
                  · ersättare för {{ namnOchParti(r.ersatt.namn, r.ersatt.parti) }}
                </span>
              </th>
              <td><Partimarkering :parti="r.parti" /><Periodmarkering v-if="r.partitillhorighet" :period="r.partitillhorighet" /></td>
              <td>
                {{ rosttext(r.rost) }}
                <Rattelsemarkering v-if="r.rattelser?.rost" :rattelse="r.rattelser.rost" falt="rost" />
              </td>
            </tr>
          </tbody>
        </table>
      </details>
    </section>

    <section v-if="b.reservationer.length" class="kort" aria-labelledby="res-rubrik" data-testid="reservationer">
      <h2 id="res-rubrik">Reservationer</h2>
      <ul class="yrkanden">
        <li v-for="(r, i) in b.reservationer" :key="i" data-testid="reservation">
          <p class="yrkandetext">{{ r.text }}</p>
          <p v-if="r.partier.length || r.personer.length" class="anteckning">
            <template v-for="p in r.partier" :key="p"><Partimarkering :parti="p" />{{ ' ' }}</template>
            <template v-for="(p, j) in r.personer" :key="p.namn">
              <template v-if="j || r.partier.length"> · </template>
              <RouterLink v-if="p.ledamot_id" :to="`/politik/ledamoter/${p.ledamot_id}`">{{ p.namn }}</RouterLink>
              <template v-else>{{ p.namn }}</template>
              {{ ' ' }}<Partimarkering :parti="p.parti" /><Periodmarkering v-if="p.partitillhorighet" :period="p.partitillhorighet" />
            </template>
          </p>
        </li>
      </ul>
    </section>

    <section class="kort" aria-labelledby="besl-rubrik" data-testid="beslutande">
      <h2 id="besl-rubrik">Beslutande vid paragrafen <span class="antal">({{ b.beslutande.length }})</span></h2>
      <p class="ingress">
        Räknat ur närvarolistan, med hänsyn till jäv och ersättare som tjänstgjorde bara vid vissa paragrafer.
      </p>
      <ul class="personer">
        <li v-for="p in b.beslutande" :key="p.namn" data-testid="person">
          <RouterLink v-if="p.ledamot_id" :to="`/politik/ledamoter/${p.ledamot_id}`">{{ p.namn }}</RouterLink>
          <template v-else>{{ p.namn }}</template>
          <Partimarkering :parti="p.parti" />
          <Harledningsmarkering v-if="p.parti_harlett" :kalla="p.parti_harlett" />
          <Periodmarkering v-if="p.partitillhorighet" :period="p.partitillhorighet" />
          <Rattelsemarkering v-if="p.rattelser?.parti" :rattelse="p.rattelser.parti" falt="parti" />
          <span v-if="p.tjanstgor_for" class="anteckning">
            tjänstgör för {{ namnOchParti(p.tjanstgor_for.namn, p.tjanstgor_for.parti) }}
          </span>
        </li>
      </ul>
      <template v-if="b.jav.length">
        <h3>Jäv</h3>
        <ul class="personer" data-testid="jav">
          <li v-for="p in b.jav" :key="p.namn">
            <RouterLink v-if="p.ledamot_id" :to="`/politik/ledamoter/${p.ledamot_id}`">{{ p.namn }}</RouterLink>
            <template v-else>{{ p.namn }}</template>
            <Partimarkering :parti="p.parti" />
            <Harledningsmarkering v-if="p.parti_harlett" :kalla="p.parti_harlett" />
            <Periodmarkering v-if="p.partitillhorighet" :period="p.partitillhorighet" />
          </li>
        </ul>
      </template>
    </section>

    <section v-if="arRedaktor" class="kort" aria-labelledby="ratt-rubrik" data-testid="ratta">
      <h2 id="ratt-rubrik">Rätta en uppgift</h2>
      <p class="ingress">
        Rättelsen sparas som utkast. Den visas för läsarna först när en annan person med rollen utgivare har granskat
        och publicerat den. Tolkningen ändras inte och visas tillsammans med rättelsen.
      </p>
      <Rattelseformular :behandling="b" @utloggad="utloggad" />
    </section>

    <nav class="blader" aria-label="Paragrafer">
      <RouterLink v-if="b.foregaende !== null" :to="lank(b.foregaende)" data-testid="foregaende">
        ‹ § {{ b.foregaende }}
      </RouterLink>
      <span v-else />
      <RouterLink v-if="b.nasta !== null" :to="lank(b.nasta)" data-testid="nasta">§ {{ b.nasta }} ›</RouterLink>
    </nav>
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
.overrubrik {
  font-size: 13px;
  color: var(--ink-secondary);
  margin: 0 0 4px;
}
.forsta-versal {
  display: inline-block;
}
.ingress {
  color: var(--ink-secondary);
  margin: 0;
  max-width: 70ch;
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
}
.kort h2 {
  margin-bottom: 12px;
}
.kort h3 {
  font-size: 14px;
  margin: 20px 0 8px;
}
.antal {
  color: var(--ink-muted);
  font-weight: 400;
}
.rattelserad {
  margin: 8px 0 0;
}
.arendetext {
  margin: 0 0 8px;
}
.beslut {
  white-space: pre-line;
  max-width: 80ch;
  margin: 0;
}
.personer {
  columns: 3 240px;
  margin: 12px 0 0;
  padding: 0;
  list-style: none;
  font-size: 13px;
}
.personer li {
  break-inside: avoid;
  padding: 2px 0;
}
.anteckning {
  display: block;
  font-size: 12px;
  color: var(--ink-muted);
}
.saknas {
  color: var(--ink-muted);
  font-style: italic;
}
.blader {
  display: flex;
  justify-content: space-between;
  font-size: 13px;
}
.blader a {
  color: var(--accent);
}
.fel {
  color: var(--status-critical);
}
.yrkanden {
  list-style: none;
  margin: 0;
  padding: 0;
}
.yrkanden li {
  padding: 8px 0;
  border-bottom: 1px solid var(--line);
}
.yrkanden li:last-child {
  border-bottom: none;
}
.yrkandetext,
.lopande {
  margin: 0;
  max-width: 80ch;
}
.yrkanden .anteckning {
  display: block;
  margin-top: 4px;
  font-size: 13px;
}
.ankare {
  color: inherit;
  text-decoration: none;
}
.ankare:hover {
  text-decoration: underline;
}
.forslag {
  display: grid;
  grid-template-columns: max-content 1fr;
  gap: 4px 16px;
  margin: 0 0 12px;
  max-width: 80ch;
}
.forslag dt {
  font-weight: 600;
  color: var(--ink-secondary);
}
.forslag dd {
  margin: 0;
}
.utfall {
  margin: 0 0 8px;
}
.tal {
  font-variant-numeric: tabular-nums;
}
.avvikelse {
  color: var(--status-warning);
  font-size: 13px;
  margin: 0 0 8px;
}
.tabell {
  border-collapse: collapse;
  font-size: 13px;
  width: 100%;
  max-width: 640px;
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
  font-weight: 400;
}
.hoger {
  text-align: right !important;
}
.ledamoter {
  margin-top: 16px;
}
.ledamoter summary {
  cursor: pointer;
  font-weight: 600;
  font-size: 14px;
  margin-bottom: 8px;
}
</style>
