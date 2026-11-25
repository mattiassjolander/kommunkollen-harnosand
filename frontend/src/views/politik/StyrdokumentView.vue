<script setup lang="ts">
import { computed, inject, ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import { EjInloggad, Saknas, hamtaStyrdokument, type Dokumentinformationsfalt, type Styrdokument } from '../../api'
import { datum } from '../../format'
import { dokumenttitel } from '../../navigering'
import Giltighetsmarkering from '../../components/Giltighetsmarkering.vue'
import Motstridighetskort from '../../components/Motstridighetskort.vue'

// Dokumentsidan för ett styrande dokument (#63): dokumentinformationen som den står i rutan på första sidan,
// giltigheten med källa, beslutet som fastställde dokumentet och versionerna med plattformens kopior.

const route = useRoute()
const utloggad = inject<() => void>('utloggad', () => {})

const d = ref<Styrdokument | null>(null)
const laddar = ref(true)
const fel = ref<string | null>(null)
const saknas = ref(false)

watch(
  () => route.params.id,
  async (id) => {
    laddar.value = true
    saknas.value = false
    fel.value = null
    try {
      d.value = await hamtaStyrdokument(Number(id))
      document.title = dokumenttitel(route.path, d.value.titel)
    } catch (e) {
      if (e instanceof EjInloggad) return utloggad()
      if (e instanceof Saknas) saknas.value = true
      else fel.value = e instanceof Error ? e.message : String(e)
    } finally {
      laddar.value = false
    }
  },
  { immediate: true },
)

const FALT: [Dokumentinformationsfalt, string][] = [
  ['dokumentnamn', 'Dokumentnamn'],
  ['dokumenttyp', 'Dokumenttyp enligt dokumentet'],
  ['faststalld_av', 'Fastställd/upprättad av'],
  ['datum', 'Datum'],
  ['diarienummer', 'Diarienummer'],
  ['dokumentansvarig', 'Dokumentansvarig/processägare'],
  ['version', 'Version enligt dokumentet'],
  ['senast_reviderad', 'Senast reviderad'],
  ['giltig_tom', 'Giltig t o m'],
  ['dokumentinformation', 'Dokumentinformation'],
  ['galler_for', 'Dokumentet gäller för'],
  ['annan_information', 'Annan information'],
]

const gallande = computed(() => d.value?.versioner[0] ?? null)
const kallaText = computed(() => {
  const k = d.value?.giltighet.kalla
  return k === 'dokumentinformationen' ? 'enligt dokumentinformationen' : k === 'titeln' ? 'enligt perioden i titeln' : null
})
const mb = (byte: number) => `${(byte / 1_000_000).toLocaleString('sv-SE', { maximumFractionDigits: 1 })} MB`
</script>

<template>
  <p v-if="laddar">Hämtar uppgifter…</p>
  <p v-else-if="saknas">Dokumentet finns inte.</p>
  <p v-else-if="fel" class="fel">Kunde inte hämta uppgifter: {{ fel }}</p>
  <template v-else-if="d">
    <header class="vyhuvud">
      <p class="tillbaka"><RouterLink to="/politik/styrande-dokument">‹ Styrande dokument</RouterLink></p>
      <h1>{{ d.titel }}</h1>
      <p class="meta" data-testid="meta">
        {{ d.kategorier.join(', ') }} ·
        <Giltighetsmarkering :giltighet="d.giltighet" />
        <template v-if="!d.borttagen">
          · <a :href="d.url" target="_blank" rel="noopener" data-testid="pdf-kommunen">PDF hos kommunen</a>
        </template>
        <template v-if="gallande">
          · <a :href="gallande.kopia" target="_blank" rel="noopener" data-testid="pdf-kopia">Plattformens kopia</a>
        </template>
      </p>
    </header>

    <section class="kort" aria-labelledby="giltighet-rubrik" data-testid="giltighet">
      <h2 id="giltighet-rubrik">Giltighet</h2>
      <p class="giltighetstext">
        {{ d.giltighet.text }}
        <template v-if="d.galler_fran"> Gäller från och med {{ datum(d.galler_fran) }} enligt dokumentinformationen.</template>
      </p>
      <p v-if="kallaText" class="not">Giltigheten är läst {{ kallaText }}.</p>
    </section>

    <section class="kort" aria-labelledby="info-rubrik" data-testid="dokumentinformation">
      <h2 id="info-rubrik">Dokumentinformation</h2>
      <p v-if="!d.dokumentinformation.ruta" class="not" data-testid="ingen-ruta">
        Dokumentet har ingen ruta med dokumentinformation på första sidan.
      </p>
      <dl v-else class="falt">
        <template v-for="[nyckel, namn] in FALT" :key="nyckel">
          <dt>{{ namn }}</dt>
          <dd :data-testid="`falt-${nyckel}`">
            <template v-if="d.dokumentinformation[nyckel]">{{ d.dokumentinformation[nyckel] }}</template>
            <span v-else class="saknas">Uppgift saknas</span>
          </dd>
        </template>
      </dl>
      <p v-if="d.dokumentinformation.ruta" class="not">
        Uppgifterna återges som de står i dokumentet och rättas inte av plattformen.
      </p>
    </section>

    <section class="kort" aria-labelledby="beslut-rubrik" data-testid="beslut">
      <h2 id="beslut-rubrik">Beslut</h2>
      <ul v-if="d.beslut.length" class="lista">
        <li v-for="b in d.beslut" :key="`${b.sammantrade_id}:${b.paragraf}`">
          <RouterLink :to="`/politik/sammantraden/${b.sammantrade_id}/paragraf/${b.paragraf}`">
            {{ b.organ.namn }} {{ datum(b.datum) }} § {{ b.paragraf }}
          </RouterLink>
          <span class="not"> ({{ b.grund }})</span>
        </li>
      </ul>
      <p v-else class="not" data-testid="inget-beslut">
        Inget beslut i protokollen har samma organ, datum och diarienummer som dokumentinformationen. Protokollen
        finns från 2022.
      </p>
    </section>

    <section class="kort" aria-labelledby="motstridighet-rubrik" data-testid="motstridigheter">
      <h2 id="motstridighet-rubrik">Motstridigheter</h2>
      <template v-if="d.motstridigheter.length">
        <p class="not forsta">
          Ställen i eller mellan reglementen och delegationsordningar som inte går ihop, enligt redaktionens analys.
          <RouterLink to="/politik/styrande-dokument/motstridigheter">Alla motstridigheter</RouterLink>
        </p>
        <Motstridighetskort v-for="m in d.motstridigheter" :key="m.id" :m="m" />
      </template>
      <p v-else class="not" data-testid="inga-motstridigheter">Redaktionen har inte publicerat några motstridigheter för dokumentet.</p>
    </section>

    <section class="kort" aria-labelledby="process-rubrik" data-testid="processer">
      <h2 id="process-rubrik">Processer</h2>
      <template v-if="d.processer.length">
        <p class="not forsta">
          Arbetsgångar som har steg ur dokumentet, enligt redaktionens analys. <span class="analysetikett">Analys</span>
        </p>
        <ul class="lista">
          <li v-for="p in d.processer" :key="p.id" data-testid="process">
            <RouterLink :to="`/politik/styrande-dokument/processer/${p.id}`">{{ p.namn }}</RouterLink>
            <span class="not"> · {{ p.steg === 1 ? '1 steg' : `${p.steg} steg` }} ur dokumentet</span>
          </li>
        </ul>
      </template>
      <p v-else class="not" data-testid="inga-processer">Dokumentet ingår inte i någon publicerad process.</p>
    </section>

    <section class="kort" aria-labelledby="version-rubrik" data-testid="versioner">
      <h2 id="version-rubrik">Versioner</h2>
      <table class="tabell">
        <thead>
          <tr>
            <th scope="col">Version</th>
            <th scope="col">Hämtad</th>
            <th scope="col">Status</th>
            <th scope="col">Fil</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="v in d.versioner" :key="v.version" data-testid="version">
            <td class="tal">{{ v.version }}</td>
            <td class="tal">{{ datum(v.hamtad) }}</td>
            <td>
              <template v-if="v.ersatt">Ersatt {{ datum(v.ersatt) }}</template>
              <template v-else-if="d.borttagen">Senaste versionen</template>
              <template v-else>Gällande</template>
              <span v-if="v.ocr" class="not"> · läst med OCR</span>
            </td>
            <td>
              <a :href="v.kopia" target="_blank" rel="noopener">Plattformens kopia</a>
              <span class="not"> · {{ v.sidor }} sidor, {{ mb(v.storlek) }}</span>
            </td>
          </tr>
        </tbody>
      </table>
      <p class="kallrad" data-testid="kallrad">
        Källa: <a :href="d.kalla.url" target="_blank" rel="noopener">harnosand.se, {{ d.kalla.titel }}</a> · Först sedd
        {{ datum(d.forst_sedd) }} · Kontrollerad {{ datum(d.kalla.kontrollerad) }}
      </p>
    </section>
  </template>
</template>

<style scoped>
.vyhuvud {
  margin-bottom: 16px;
}
.tillbaka {
  margin: 0 0 4px;
  font-size: 13px;
}
.meta {
  color: var(--ink-secondary);
  font-size: 13px;
  margin: 4px 0 0;
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
.giltighetstext {
  margin: 0;
}
.falt {
  display: grid;
  grid-template-columns: minmax(160px, max-content) minmax(0, 1fr);
  gap: 6px 24px;
  margin: 0;
  font-size: 13px;
}
.falt dt {
  color: var(--ink-secondary);
}
.falt dd {
  margin: 0;
}
.saknas {
  color: var(--ink-muted);
}
.not {
  color: var(--ink-muted);
  font-size: 13px;
  margin: 8px 0 0;
}
.forsta {
  margin: 0 0 12px;
}
.analysetikett {
  font-size: 12px;
  font-weight: 600;
  color: var(--ink-secondary);
  border: 1px dashed var(--line-strong);
  border-radius: var(--radius);
  padding: 0 6px;
}
.lista {
  margin: 0;
  padding-left: 20px;
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
}
.kallrad {
  margin: 12px 0 0;
  font-size: 12px;
  color: var(--ink-muted);
}
.fel {
  color: var(--status-critical);
}
@media (max-width: 600px) {
  .falt {
    grid-template-columns: minmax(0, 1fr);
  }
  .falt dd {
    margin-bottom: 8px;
  }
}
</style>
