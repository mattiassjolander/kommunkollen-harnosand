<script setup lang="ts">
// Sammansättning (#65): kön och ålder bland kandidater, valda och tjänstgörande, per parti, organ och
// mandatperiod. Mandatperiod och organ speglas i URL:en (design.md, Filter). Bara sammanställd statistik visas.
import { computed, inject, ref, watch, type Ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { EjInloggad, hamtaSammansattning, type Jag, type Sammansattning } from '../../api'
import { datum } from '../../format'
import Sammansattningsled from '../../components/Sammansattningsled.vue'
import SammansattningRedaktion from '../../components/SammansattningRedaktion.vue'

const route = useRoute()
const router = useRouter()
const utloggad = inject<() => void>('utloggad', () => {})
const jag = inject<Ref<Jag | null>>('jag', ref(null))
const arRedaktor = computed(() => jag.value?.roller.includes('redaktor') ?? false)
const arUtgivare = computed(() => jag.value?.roller.includes('utgivare') ?? false)

function fraga(namn: string) {
  return computed<string>({
    get: () => (typeof route.query[namn] === 'string' ? (route.query[namn] as string) : ''),
    set: (v) => router.replace({ query: { ...route.query, [namn]: v || undefined } }),
  })
}
const period = fraga('period')
const organ = fraga('organ')

const s = ref<Sammansattning | null>(null)
const fel = ref<string | null>(null)
const laddar = ref(true)

async function ladda() {
  laddar.value = true
  fel.value = null
  try {
    s.value = await hamtaSammansattning(period.value, organ.value)
  } catch (e) {
    if (e instanceof EjInloggad) return utloggad()
    fel.value = e instanceof Error ? e.message : String(e)
  } finally {
    laddar.value = false
  }
}
watch([period, organ], ladda, { immediate: true })

const valdPeriod = computed({
  get: () => period.value || String(s.value?.period.ar ?? ''),
  set: (v: string) => (period.value = v),
})
const valtOrgan = computed({
  get: () => organ.value || s.value?.organ.id || '',
  set: (v: string) => (organ.value = v),
})
const rubrik = computed(() => (s.value ? `${s.value.organ.namn}, ${s.value.period.namn}` : ''))
</script>

<template>
  <header class="vyhuvud">
    <h1>Sammansättning</h1>
    <p class="ingress">
      Hur kandidater, valda och tjänstgörande ledamöter fördelar sig på kön och ålder, per parti, organ och
      mandatperiod. De röstberättigade i Härnösand visas som jämförelse.
    </p>
  </header>

  <div class="filter" role="group" aria-label="Filter">
    <label>
      Mandatperiod
      <select v-model="valdPeriod" data-testid="filter-period">
        <option v-for="p in s?.perioder ?? []" :key="p.ar" :value="String(p.ar)">{{ p.namn }}</option>
      </select>
    </label>
    <label>
      Organ
      <select v-model="valtOrgan" data-testid="filter-organ">
        <option v-for="o in s?.organlista ?? []" :key="o.id" :value="o.id">{{ o.namn }}</option>
      </select>
    </label>
  </div>

  <p v-if="fel" class="fel" role="alert">{{ fel }}</p>
  <p v-else-if="laddar && !s">Hämtar sammansättningen…</p>
  <template v-else-if="s">
    <p class="konstext" role="note" data-testid="konstext">
      {{ s.konstext }}. Åldern är åldern på valdagen {{ datum(s.period.valdag) }}, och för tjänstgörande åldern vid
      sammanträdet. Personer utan uppgift ingår som "uppgift saknas".
    </p>

    <h2 class="ledrubrik">Kandidater</h2>
    <template v-if="s.kandidater">
      <Sammansattningsled
        id="kandidater"
        :rubrik="`Alla kandidater, kommunfullmäktige ${s.period.valdag.slice(0, 4)}`"
        beskrivning="Alla som stod på ett partis lista till kommunfullmäktige i valet."
        :led="s.kandidater.alla"
        :referens="s.referens"
        :aldersgrupper="s.aldersgrupper"
        :period="s.period.namn"
      />
      <Sammansattningsled
        v-if="s.kandidater.topp"
        id="topp"
        :rubrik="`De tio högst placerade per parti, ${s.period.valdag.slice(0, 4)}`"
        beskrivning="Kandidaterna på plats 1–10 på varje partis lista."
        :led="s.kandidater.topp"
        :referens="s.referens"
        :aldersgrupper="s.aldersgrupper"
        :period="s.period.namn"
      />
      <p v-else class="saknas">
        De tio högst placerade visas bara för 2026. Valmyndigheten har gallrat kandidaternas uppgifter från 2022.
      </p>
    </template>
    <p v-else class="saknas" data-testid="inga-kandidater">
      Kandidaterna står på listor till kommunfullmäktige. {{ s.organ.namn }} väljs av fullmäktige och har inga egna
      kandidater.
    </p>

    <h2 class="ledrubrik">Valda</h2>
    <template v-if="s.valda?.vid_start">
      <Sammansattningsled
        id="valda"
        :rubrik="`Valda ledamöter vid mandatperiodens start, ${rubrik}`"
        beskrivning="De ordinarie ledamöter som valdes in i fullmäktige, enligt Valmyndigheten."
        :led="s.valda.vid_start"
        :referens="s.referens"
        :aldersgrupper="s.aldersgrupper"
        :period="s.period.namn"
      />
      <Sammansattningsled
        v-if="s.valda.med_eftertradare && s.valda.med_eftertradare.totalt.antal !== s.valda.vid_start.totalt.antal"
        id="eftertradare"
        :rubrik="`Valda ledamöter med efterträdare under perioden, ${rubrik}`"
        beskrivning="Ledamöterna vid starten och de som efterträtt ledamöter som avgått."
        :led="s.valda.med_eftertradare"
        :referens="s.referens"
        :aldersgrupper="s.aldersgrupper"
        :period="s.period.namn"
      />
    </template>
    <Sammansattningsled
      v-else-if="s.valda?.enligt_protokollen"
      id="valda"
      :rubrik="`Ordinarie ledamöter enligt närvarolistorna, ${rubrik}`"
      beskrivning="Nämndernas och kommunstyrelsens ledamöter väljs av fullmäktige och finns inte i Valmyndighetens filer. Här räknas de som står som ordinarie ledamöter (inte ersättare) i närvarolistorna under perioden."
      :led="s.valda.enligt_protokollen"
      :referens="s.referens"
      :aldersgrupper="s.aldersgrupper"
      :period="s.period.namn"
    />
    <p v-else class="saknas">Uppgift saknas för perioden.</p>

    <h2 class="ledrubrik">Tjänstgörande</h2>
    <Sammansattningsled
      v-if="s.tjanstgorande"
      id="tjanstgorande"
      :rubrik="`Tjänstgörande vid sammanträdena, ${rubrik}`"
      beskrivning="De som deltog i besluten enligt närvarolistorna, ordinarie ledamöter och tjänstgörande ersättare. Varje person räknas en gång per sammanträde, så den som tjänstgjort ofta väger tyngre. Partiet är det som gäller vid sammanträdet."
      :led="s.tjanstgorande"
      :referens="s.referens"
      :aldersgrupper="s.aldersgrupper"
      :period="s.period.namn"
      enhet="tjänstgöringar"
    />
    <p v-else class="saknas" data-testid="inga-tjanstgorande">Inga sammanträden med närvarolista under perioden.</p>

    <SammansattningRedaktion
      v-if="arRedaktor || arUtgivare"
      :redaktor="arRedaktor"
      :utgivare="arUtgivare"
      :epost="jag?.epost ?? null"
      @andrat="ladda"
    />
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
  display: flex;
  gap: 16px;
  flex-wrap: wrap;
  margin-bottom: 16px;
}
.filter label {
  display: grid;
  gap: 4px;
  font-size: 13px;
  color: var(--ink-secondary);
}
.filter select {
  font: inherit;
  font-size: 14px;
  color: var(--ink);
  background: var(--surface);
  border: 1px solid var(--line);
  border-radius: var(--radius);
  padding: 6px 8px;
}
.konstext {
  font-size: 13px;
  color: var(--ink-secondary);
  margin: 0 0 16px;
  max-width: 90ch;
}
.ledrubrik {
  font-size: 16px;
  margin: 24px 0 8px;
}
.saknas {
  color: var(--ink-muted);
  font-style: italic;
  font-size: 13px;
}
.fel {
  color: var(--status-critical);
}
</style>
