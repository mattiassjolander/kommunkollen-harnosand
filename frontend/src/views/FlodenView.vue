<script setup lang="ts">
import { computed, inject, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { EjInloggad, hamtaFloden, type Flode, type Flodesmodell } from '../api'
import { siffra, tal, visningsskala } from '../format'
import Sankey from '../components/Sankey.vue'
import StatusMarkering from '../components/StatusMarkering.vue'

const route = useRoute()
const router = useRouter()
const modell = ref<Flodesmodell | null>(null)
const laddar = ref(true)
const fel = ref<string | null>(null)
const valt = ref<Flode | null>(null)
const utloggad = inject<() => void>('utloggad', () => {})

async function ladda(ar?: string) {
  laddar.value = true
  try {
    modell.value = await hamtaFloden(ar)
    valt.value = null
  } catch (e) {
    if (e instanceof EjInloggad) return utloggad()
    fel.value = e instanceof Error ? e.message : String(e)
  } finally {
    laddar.value = false
  }
}
onMounted(() => ladda((route.query.ar as string) || undefined))

// Valt år speglas i URL:en.
const ar = computed({
  get: () => modell.value?.ar ?? '',
  set: (v: string) => {
    router.replace({ query: { ...route.query, ar: v } })
    ladda(v)
  },
})
watch(
  () => route.query.ar,
  (v) => {
    if (v && v !== modell.value?.ar) ladda(v as string)
  },
)

const skala = visningsskala('tkr')
const mnkr = (tkr: number) => tal(tkr * skala.faktor, skala.enhet)
const titel = (id: string) => modell.value?.noder.find((n) => n.id === id)?.titel ?? id
const nod = (f: Flode) => modell.value?.noder.find((n) => n.id === (f.till === 'kommunen' ? f.fran : f.till))
const procent = (v: number) => `${siffra(v * 100, '%')} %`
const kronor = (v: number | null) => (v === null ? 'Uppgift saknas' : tal(v, 'kr'))
</script>

<template>
  <header class="vyhuvud">
    <h1>Ekonomiska flöden</h1>
    <p class="ingress">
      Hur kommunens intäkter under ett år används. Bredden på varje flöde motsvarar beloppet. Klicka på ett flöde för
      att se belopp, andel och källa.
    </p>
  </header>

  <p v-if="laddar && !modell">Hämtar uppgifter…</p>
  <p v-else-if="fel" class="fel">Kunde inte hämta uppgifter: {{ fel }}</p>
  <p v-else-if="modell && !modell.tillgangliga_ar.length" data-testid="tomt">
    Uppgift saknas. Ingen insamling har hämtat räkenskapssammandraget än.
  </p>

  <template v-else-if="modell">
    <div class="filterrad">
      <label>
        År
        <select v-model="ar" data-testid="ar">
          <option v-for="a in [...modell.tillgangliga_ar].reverse()" :key="a.ar" :value="a.ar">
            {{ a.ar }}{{ a.fullstandig ? '' : ' (ofullständigt underlag)' }}
          </option>
        </select>
      </label>
      <ul class="markeringar" data-testid="flodesinfo">
        <li>{{ modell.flodestyp === 'brutto' ? 'Bruttoflöden' : 'Nettoflöden' }}</li>
        <li>{{ modell.indelning }}</li>
        <li>Löpande priser</li>
      </ul>
    </div>

    <section v-if="!modell.fullstandig" class="kort ofullstandig" data-testid="ofullstandigt">
      <StatusMarkering status="delvis_fel" :text="`Ofullständigt underlag för ${modell.ar}`" />
      <p>
        Flödena visas inte för det här året, eftersom uppgifter saknas i underlaget. De fylls inte ut med uppskattningar.
      </p>
      <ul>
        <li v-for="s in modell.saknas" :key="s">{{ s }}</li>
      </ul>
    </section>

    <div v-else class="yta">
      <section class="kort diagram">
        <Sankey :noder="modell.noder" :floden="modell.floden" :valt="valt" @valj="valt = $event" />
      </section>

      <aside class="kort detalj" data-testid="flodesdetalj" aria-live="polite">
        <template v-if="valt">
          <h2>{{ titel(valt.fran) }} → {{ titel(valt.till) }}</h2>
          <dl>
            <dt>Belopp</dt>
            <dd class="tal" data-testid="belopp">{{ mnkr(valt.belopp) }}</dd>
            <dt>Andel av totalen</dt>
            <dd class="tal">{{ procent(valt.andel) }}</dd>
            <dt>Per invånare</dt>
            <dd class="tal">{{ kronor(valt.kr_per_invanare) }}</dd>
          </dl>
          <p v-if="nod(valt)?.forklaring" class="forklaring">{{ nod(valt)?.forklaring }}</p>
          <p class="kallrad">
            Källa:
            <template v-for="(k, i) in valt.kallor" :key="k.url">
              <template v-if="i">, </template>
              <a :href="k.url" target="_blank" rel="noopener">{{ k.titel }}</a>
            </template>
            · {{ modell.ar }} · tkr i löpande priser, visas som mnkr
          </p>
        </template>
        <p v-else class="tips">Klicka på ett flöde i diagrammet för att se belopp, andel, kronor per invånare och källa.</p>
        <p v-if="modell.invanare" class="kallrad">
          Totalt {{ mnkr(modell.totalt ?? 0) }} · {{ tal(modell.invanare) }} invånare 31 december {{ modell.ar }}
          (Kolada N01951)
        </p>
      </aside>
    </div>

    <details v-if="modell.fullstandig" class="kort tabellvy">
      <summary>Visa flödena som tabell</summary>
      <table class="tabell" data-testid="flodestabell">
        <thead>
          <tr>
            <th scope="col">Från</th>
            <th scope="col">Till</th>
            <th scope="col" class="hoger">mnkr</th>
            <th scope="col" class="hoger">Andel</th>
            <th scope="col" class="hoger">kr/inv</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="f in modell.floden" :key="f.fran + f.till" :class="{ vald: valt === f }" @click="valt = f">
            <td>{{ titel(f.fran) }}</td>
            <td>{{ titel(f.till) }}</td>
            <td class="tal hoger">{{ siffra(f.belopp * skala.faktor, 'mnkr') }}</td>
            <td class="tal hoger">{{ procent(f.andel) }}</td>
            <td class="tal hoger">{{ f.kr_per_invanare === null ? 'Uppgift saknas' : siffra(f.kr_per_invanare, 'kr') }}</td>
          </tr>
        </tbody>
      </table>
    </details>
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
.filterrad {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 12px 24px;
  margin-bottom: 24px;
  padding-bottom: 16px;
  border-bottom: 1px solid var(--line);
}
.filterrad label {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  color: var(--ink-secondary);
}
.filterrad select {
  font: inherit;
  padding: 4px 8px;
  border: 1px solid var(--line-strong);
  border-radius: var(--radius);
  background: var(--surface-raised);
  color: var(--ink);
}
.markeringar {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin: 0;
  padding: 0;
  list-style: none;
  font-size: 12px;
}
.markeringar li {
  border: 1px solid var(--line-strong);
  border-radius: 999px;
  padding: 2px 10px;
  color: var(--ink-secondary);
}
.kort {
  background: var(--surface);
  border: 1px solid var(--line);
  border-radius: var(--radius);
  padding: 24px;
}
.yta {
  display: grid;
  grid-template-columns: minmax(0, 1fr) 300px;
  gap: 16px;
  align-items: start;
}
@media (max-width: 1100px) {
  .yta {
    grid-template-columns: 1fr;
  }
}
.detalj h2 {
  font-size: 15px;
  margin-bottom: 12px;
}
.detalj dl {
  display: grid;
  grid-template-columns: auto 1fr;
  gap: 4px 16px;
  margin: 0 0 12px;
}
.detalj dt {
  color: var(--ink-secondary);
}
.detalj dd {
  margin: 0;
  text-align: right;
  font-weight: 600;
}
.forklaring,
.tips {
  color: var(--ink-secondary);
  margin: 0 0 12px;
}
.kallrad {
  font-size: 12px;
  color: var(--ink-muted);
  margin: 8px 0 0;
}
.kallrad a {
  color: inherit;
}
.ofullstandig p {
  color: var(--ink-secondary);
}
.tabellvy {
  margin-top: 16px;
}
.tabellvy summary {
  cursor: pointer;
  font-weight: 600;
}
.tabell {
  border-collapse: collapse;
  font-size: 13px;
  width: 100%;
  margin-top: 12px;
}
.tabell th,
.tabell td {
  padding: 4px 16px 4px 0;
  border-bottom: 1px solid var(--line);
  text-align: left;
}
.tabell th {
  color: var(--ink-secondary);
  font-weight: 600;
}
.tabell tbody tr {
  cursor: pointer;
}
.tabell tbody tr:hover,
.tabell tbody tr.vald {
  background: var(--accent-wash);
}
.hoger {
  text-align: right !important;
}
.fel {
  color: var(--status-critical);
}
</style>
