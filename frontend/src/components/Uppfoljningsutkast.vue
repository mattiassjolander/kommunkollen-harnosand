<script setup lang="ts">
// Granskning av budget jämfört med utfall (#83). Uppföljningen läses in ur uppfoljning.json och rättas i filen;
// här kontrolleras varje siffra mot sidan i dokumentet, och en utgivare som inte läst in den granskar, publicerar
// och vid behov återkallar den.
import { computed, inject, onMounted, reactive, ref, type Ref } from 'vue'
import {
  EjInloggad,
  aterkallaUppfoljning,
  granskaUppfoljning,
  hamtaUppfoljningsutkast,
  publiceraUppfoljning,
  type Jag,
  type Sidbelopp,
  type Uppfoljningsutkast,
} from '../api'
import { datumTid } from '../format'

const utloggad = inject<() => void>('utloggad', () => {})
const jag = inject<Ref<Jag | null>>('jag', ref(null))
const arUtgivare = computed(() => jag.value?.roller.includes('utgivare') ?? false)
const oppna = ref<Uppfoljningsutkast[]>([])
const publicerade = ref<Uppfoljningsutkast[]>([])
const meddelande = reactive<Record<number, string>>({})
const motivering = reactive<Record<number, string>>({})
const fel = ref<string | null>(null)

async function ladda() {
  try {
    const [u, g, p] = await Promise.all([
      hamtaUppfoljningsutkast('utkast'),
      hamtaUppfoljningsutkast('granskad'),
      hamtaUppfoljningsutkast('publicerad'),
    ])
    oppna.value = [...u, ...g]
    publicerade.value = p
  } catch (e) {
    if (e instanceof EjInloggad) return utloggad()
    fel.value = e instanceof Error ? e.message : String(e)
  }
}
onMounted(ladda)

const egen = (u: Uppfoljningsutkast) => !!jag.value && u.redaktorer.includes(jag.value.epost)
const nr = (v: number | null | undefined) => (v === null || v === undefined ? '–' : String(v).replace('.', ','))
const lank = (url: string | undefined, b: Sidbelopp | null) => (url && b?.sida ? `${url}#page=${b.sida}` : undefined)

async function steg(u: Uppfoljningsutkast, gor: () => Promise<Uppfoljningsutkast>, klart: string) {
  meddelande[u.id] = ''
  try {
    await gor()
    meddelande[u.id] = klart
    await ladda()
  } catch (e) {
    if (e instanceof EjInloggad) return utloggad()
    meddelande[u.id] = e instanceof Error ? e.message : String(e)
  }
}
</script>

<template>
  <p v-if="fel" class="fel" role="alert">Kunde inte hämta uppföljningen: {{ fel }}</p>
  <section v-if="oppna.length" aria-labelledby="uppfoljning-rubrik">
    <h2 id="uppfoljning-rubrik" class="sektion">Budget och utfall</h2>
    <ul class="lista">
      <li v-for="u in oppna" :key="u.id" class="kort" data-testid="uppfoljningsutkast" :data-budgetar="u.budgetar">
        <div class="huvud">
          <strong>Budget och utfall {{ u.budgetar }}</strong>
          <span class="etikett" :data-status="u.status">{{ u.status === 'utkast' ? 'Utkast' : 'Granskad' }}</span>
          <span class="meta">{{ u.filnamn }}</span>
        </div>
        <p class="meta">
          Läst in av {{ u.redaktorer.join(', ') }}, senast {{ datumTid(u.andrad) }}.
          <template v-if="u.granskad_av">Granskat av {{ u.granskad_av }}.</template>
          Rätta i filen och läs in den igen.
        </p>
        <p v-if="u.andring" class="meta">Ny version av den publicerade: {{ u.andring.motivering }}</p>
        <p class="meta">
          <template v-if="u.dokument.arsredovisning">
            <a :href="u.dokument.arsredovisning.url" target="_blank" rel="noopener">{{ u.dokument.arsredovisning.titel }}</a>.
          </template>
          <template v-if="u.dokument.delarsrapport">
            <a :href="u.dokument.delarsrapport.url" target="_blank" rel="noopener">{{ u.dokument.delarsrapport.titel }}</a>.
          </template>
          <template v-if="u.antagen">Antagen budget: {{ u.antagen.titel }}.</template>
          <template v-else>Inget antaget budgetförslag finns för {{ u.budgetar }}.</template>
        </p>
        <div class="rulla">
          <table class="tabell">
            <thead>
              <tr>
                <th scope="col">Post</th>
                <th scope="col" class="num">Antagen</th>
                <th scope="col" class="num">Budget</th>
                <th scope="col" class="num">Utfall</th>
                <th scope="col" class="num">Avvikelse enligt dokumentet</th>
                <th scope="col" class="num">Räknad</th>
                <th scope="col" class="num">Prognosavvikelse</th>
              </tr>
            </thead>
            <tbody>
              <tr>
                <th scope="row">Årets resultat</th>
                <td class="num">{{ nr(u.berakning.resultat.antagen?.mnkr) }}</td>
                <td class="num"><a v-if="u.berakning.resultat.reviderad" :href="lank(u.dokument.arsredovisning?.url, u.berakning.resultat.reviderad)" target="_blank" rel="noopener">{{ nr(u.berakning.resultat.reviderad.mnkr) }}</a><template v-else>–</template></td>
                <td class="num"><a v-if="u.berakning.resultat.utfall" :href="lank(u.dokument.arsredovisning?.url, u.berakning.resultat.utfall)" target="_blank" rel="noopener">{{ nr(u.berakning.resultat.utfall.mnkr) }}</a><template v-else>–</template></td>
                <td class="num">{{ nr(u.berakning.resultat.kontroll?.angiven) }}</td>
                <td class="num" :data-avviker="u.berakning.resultat.kontroll && !u.berakning.resultat.kontroll.stammer ? 'ja' : undefined">{{ nr(u.berakning.resultat.avvikelse_reviderad?.mnkr) }}</td>
                <td class="num"><a v-if="u.berakning.resultat.prognos" :href="lank(u.dokument.delarsrapport?.url, u.berakning.resultat.prognos)" target="_blank" rel="noopener">{{ nr(u.berakning.resultat.prognosavvikelse?.mnkr) }}</a><template v-else>–</template></td>
              </tr>
              <tr v-for="n in u.berakning.namnder" :key="n.organ" :data-organ="n.organ">
                <th scope="row">{{ n.organ }}</th>
                <td class="num">{{ nr(n.antagen?.mnkr) }}</td>
                <td class="num"><a v-if="n.reviderad" :href="lank(u.dokument.arsredovisning?.url, n.reviderad)" target="_blank" rel="noopener">{{ nr(n.reviderad.mnkr) }}</a><template v-else>–</template></td>
                <td class="num"><a v-if="n.utfall" :href="lank(u.dokument.arsredovisning?.url, n.utfall)" target="_blank" rel="noopener">{{ nr(n.utfall.mnkr) }}</a><template v-else>–</template></td>
                <td class="num">{{ nr(n.kontroll?.angiven) }}</td>
                <td class="num" :data-avviker="n.kontroll && !n.kontroll.stammer ? 'ja' : undefined" data-testid="uppfoljning-raknad">{{ nr(n.avvikelse_reviderad?.mnkr) }}</td>
                <td class="num"><a v-if="n.prognosavvikelse" :href="lank(u.dokument.delarsrapport?.url, n.prognosavvikelse)" target="_blank" rel="noopener">{{ nr(n.prognosavvikelse.mnkr) }}</a><template v-else>–</template></td>
              </tr>
            </tbody>
          </table>
        </div>
        <p class="meta">
          Räknad avvikelse är budget minus nettokostnad för nämnderna och resultat minus budget för resultatet. Markerade
          rader skiljer sig mer än avrundningen från dokumentets avvikelse.
          <template v-if="u.berakning.utan_uppfoljning.length">
            I årsplanen men inte i filen: {{ u.berakning.utan_uppfoljning.map((x) => x.organ).join(', ') }}.
          </template>
        </p>
        <div class="knappar">
          <button v-if="arUtgivare && u.status === 'utkast'" type="button" :disabled="egen(u)" :title="egen(u) ? 'Du har läst in uppföljningen' : ''" data-testid="granska-uppfoljning" @click="steg(u, () => granskaUppfoljning(u.id), 'Granskat.')">Granska</button>
          <button v-if="arUtgivare && u.status === 'granskad'" type="button" :disabled="egen(u)" data-testid="publicera-uppfoljning" @click="steg(u, () => publiceraUppfoljning(u.id), 'Publicerat.')">Publicera</button>
          <span v-if="meddelande[u.id]" class="meddelande" role="status">{{ meddelande[u.id] }}</span>
        </div>
      </li>
    </ul>
  </section>
  <section v-if="arUtgivare && publicerade.length" aria-labelledby="uppfoljning-publicerad-rubrik">
    <h2 id="uppfoljning-publicerad-rubrik" class="sektion">Publicerad budget och utfall</h2>
    <ul class="lista">
      <li v-for="u in publicerade" :key="u.id" class="kort" data-testid="publicerad-uppfoljning">
        <div class="huvud">
          <strong>Budget och utfall {{ u.budgetar }}</strong>
          <RouterLink :to="{ path: '/ekonomi/budget-och-utfall', query: { ar: u.budgetar } }">Visa</RouterLink>
        </div>
        <form class="knappar" @submit.prevent="steg(u, () => aterkallaUppfoljning(u.id, motivering[u.id] ?? ''), 'Återkallat.')">
          <input v-model="motivering[u.id]" aria-label="Motivering" placeholder="Varför återkallas uppgifterna?" />
          <button type="submit">Återkalla</button>
          <span v-if="meddelande[u.id]" class="meddelande" role="status">{{ meddelande[u.id] }}</span>
        </form>
      </li>
    </ul>
  </section>
</template>

<style scoped>
.sektion {
  font-size: 16px;
  margin: 24px 0 8px;
}
.lista {
  list-style: none;
  padding: 0;
  margin: 0;
}
.kort {
  background: var(--surface);
  border: 1px solid var(--line);
  border-radius: var(--radius);
  padding: 16px 20px;
  margin-bottom: 12px;
}
.huvud {
  display: flex;
  flex-wrap: wrap;
  gap: 8px 12px;
  align-items: baseline;
}
.etikett {
  font-size: 12px;
  padding: 1px 8px;
  border: 1px solid var(--line-strong);
  border-radius: 999px;
}
.meta {
  font-size: 13px;
  color: var(--ink-secondary);
  margin: 8px 0;
}
.rulla {
  overflow-x: auto;
}
.tabell {
  border-collapse: collapse;
  width: 100%;
  font-size: 13px;
}
.tabell th,
.tabell td {
  text-align: left;
  padding: 4px 8px;
  border-bottom: 1px solid var(--line);
}
.tabell tbody th {
  font-weight: 400;
}
.tabell .num {
  text-align: right;
  font-variant-numeric: tabular-nums;
  white-space: nowrap;
}
.tabell a {
  color: inherit;
}
[data-avviker='ja'] {
  font-weight: 600;
  outline: 2px solid var(--line-strong);
}
.knappar {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  align-items: center;
  margin-top: 8px;
}
.knappar input {
  font: inherit;
  font-size: 13px;
  min-width: 260px;
  padding: 4px 8px;
  border: 1px solid var(--line-strong);
  border-radius: var(--radius);
  background: var(--surface);
  color: var(--ink);
}
button {
  font: inherit;
  font-size: 13px;
  padding: 4px 10px;
  border: 1px solid var(--line-strong);
  border-radius: var(--radius);
  background: var(--surface);
  color: var(--ink);
  cursor: pointer;
}
button:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}
.meddelande {
  font-size: 13px;
}
</style>
