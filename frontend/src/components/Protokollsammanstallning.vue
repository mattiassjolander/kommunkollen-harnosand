<script setup lang="ts">
// Protokollsammanställningen (#195) som ett kort högst upp på sammanträdessidan. Talen räknas i backend
// (protokollsammanstallning.py) med publicerade rättelser. Varje tal är en knapp som visar bara de paragraferna i
// listan nedanför, och filtret speglas i URL:en (`visa=`). Kortet bär samma markering som protokollet (#176).
// Reserverande partier står som förkortningar i alfabetisk ordning, utan partifärg (design.md).
import { computed } from 'vue'
import type { Sammanstallning, Sammanstallningsfilter } from '../api'
import { langdtext } from '../format'
import Tolkningsmarkering from './Tolkningsmarkering.vue'

const props = defineProps<{
  sammantradeId: number
  sammanstallning: Sammanstallning | null
  ejTolkad: boolean
  ocr?: boolean
  granskad?: string | null
  modelValue: Sammanstallningsfilter | ''
}>()
const emit = defineEmits<{ 'update:modelValue': [Sammanstallningsfilter | ''] }>()

function valj(f: Sammanstallningsfilter) {
  emit('update:modelValue', props.modelValue === f ? '' : f)
}

const n = (antal: number, en: string, flera: string) => `${antal} ${antal === 1 ? en : flera}`

const huvudtal = computed(() => {
  const s = props.sammanstallning
  if (!s) return []
  return [
    { filter: 'arenden', tal: s.arenden, text: `${s.arenden === 1 ? 'ärende' : 'ärenden'} av ${n(s.paragrafer, 'paragraf', 'paragrafer')}` },
    { filter: 'beslut', tal: s.beslut, text: 'beslut' },
    { filter: 'forslag_vidare', tal: s.forslag_vidare, text: 'förslag vidare' },
    { filter: 'oenighet', tal: s.oenighet.paragrafer, text: 'med oenighet' },
  ] as { filter: Sammanstallningsfilter; tal: number; text: string }[]
})

const beslutsgang = computed(() => {
  const b = props.sammanstallning?.beslutsgang
  if (!b) return []
  return [
    { filter: 'aterremitterad', text: n(b.aterremitterade, 'återremitterat', 'återremitterade'), tal: b.aterremitterade },
    { filter: 'bordlagd', text: n(b.bordlagda, 'bordlagt', 'bordlagda'), tal: b.bordlagda },
    { filter: 'jav', text: n(b.jav, 'jäv anmält', 'jäv anmälda'), tal: b.jav },
    { filter: 'motioner', text: n(b.motioner, 'ny motion', 'nya motioner'), tal: b.motioner },
    { filter: 'medborgarforslag', text: n(b.medborgarforslag, 'nytt medborgarförslag', 'nya medborgarförslag'), tal: b.medborgarforslag },
    { filter: 'interpellationer', text: n(b.interpellationer, 'ny interpellation', 'nya interpellationer'), tal: b.interpellationer },
  ] as { filter: Sammanstallningsfilter; text: string; tal: number }[]
})

// Förslagen vidare grupperade på organet de går till.
const vidare = computed(() => {
  const grupper = new Map<string, Sammanstallning['skickas_vidare']>()
  for (const f of props.sammanstallning?.skickas_vidare ?? []) grupper.set(f.till, [...(grupper.get(f.till) ?? []), f])
  return [...grupper.entries()]
})
</script>

<template>
  <section class="kort sammanstallning" aria-labelledby="sammanst-rubrik" data-testid="sammanstallning">
    <div class="huvud">
      <h2 id="sammanst-rubrik">Sammanställning</h2>
      <Tolkningsmarkering v-if="!ejTolkad" :ocr="ocr" :granskad="granskad" prefix="sammanstallning-" />
    </div>

    <p v-if="ejTolkad || !sammanstallning" class="ingen" data-testid="ingen-sammanstallning">
      Ingen sammanställning: protokollet kunde inte tolkas automatiskt.
    </p>

    <template v-else>
      <div class="huvudtal">
        <button
          v-for="t in huvudtal"
          :key="t.filter"
          type="button"
          class="tal"
          :aria-pressed="modelValue === t.filter"
          :data-testid="`tal-${t.filter}`"
          @click="valj(t.filter)"
        >
          <span class="v">{{ t.tal }}</span>
          <span class="e">{{ t.text }}</span>
        </button>
      </div>

      <div class="rad" data-testid="rad-oenighet">
        <span class="radrubrik">Oenighet</span>
        <span v-if="sammanstallning.oenighet.enigt" class="enigt" data-testid="enigt">Enigt i alla ärenden</span>
        <template v-else>
          <button
            v-if="sammanstallning.oenighet.voteringar"
            type="button"
            class="chip votering"
            :aria-pressed="modelValue === 'votering'"
            data-testid="chip-votering"
            @click="valj('votering')"
          >
            Votering · {{ sammanstallning.oenighet.voteringar }}
          </button>
          <button
            v-if="sammanstallning.oenighet.reservationer"
            type="button"
            class="chip reservation"
            :aria-pressed="modelValue === 'reservation'"
            data-testid="chip-reservation"
            @click="valj('reservation')"
          >
            Reservation · {{ sammanstallning.oenighet.reservationer
            }}<template v-if="sammanstallning.oenighet.partier.length">
              ({{ sammanstallning.oenighet.partier.join(', ') }})</template
            >
          </button>
          <button
            v-if="sammanstallning.oenighet.paragrafer"
            type="button"
            class="chip oenighet"
            :aria-pressed="modelValue === 'oenighet'"
            data-testid="chip-oenighet"
            @click="valj('oenighet')"
          >
            Oenighet · {{ sammanstallning.oenighet.paragrafer }}
          </button>
        </template>
      </div>

      <div class="rad" data-testid="rad-beslutsgang">
        <span class="radrubrik">Beslutsgång</span>
        <template v-for="b in beslutsgang" :key="b.filter">
          <button
            v-if="b.tal"
            type="button"
            class="lank"
            :aria-pressed="modelValue === b.filter"
            :data-testid="`tal-${b.filter}`"
            @click="valj(b.filter)"
          >
            {{ b.text }}
          </button>
          <span v-else class="noll">{{ b.text }}</span>
        </template>
      </div>

      <div class="rad" data-testid="rad-sammantradet">
        <span class="radrubrik">Sammanträdet</span>
        <span v-if="sammanstallning.sammantradet.langd_minuter" data-testid="langd">
          {{ langdtext(sammanstallning.sammantradet.langd_minuter) }}
        </span>
        <span>{{ sammanstallning.sammantradet.beslutande }} beslutande</span>
        <span>{{ sammanstallning.sammantradet.tjanstgorande_ersattare }} tjänstgörande ersättare</span>
        <button
          v-if="sammanstallning.sammantradet.informationsarenden"
          type="button"
          class="lank"
          :aria-pressed="modelValue === 'information'"
          data-testid="tal-information"
          @click="valj('information')"
        >
          {{ n(sammanstallning.sammantradet.informationsarenden, 'informationsärende', 'informationsärenden') }}
        </button>
        <span v-else class="noll">0 informationsärenden</span>
      </div>

      <div v-if="vidare.length || sammanstallning.kallelsen.ej_behandlade.length" class="vidare">
        <div v-if="vidare.length" data-testid="skickas-vidare">
          <template v-for="[till, forslag] in vidare" :key="till">
            <h3>Skickas vidare till {{ till.toLowerCase() }}</h3>
            <ul>
              <li v-for="f in forslag" :key="f.paragraf">
                <RouterLink :to="`/politik/sammantraden/${sammantradeId}/paragraf/${f.paragraf}`">§ {{ f.paragraf }} {{ f.rubrik || 'Rubrik saknas' }}</RouterLink>
              </li>
            </ul>
          </template>
          <RouterLink to="/politik/kommande" class="liten">Se dem i Kommande ärenden ›</RouterLink>
        </div>
        <div v-if="sammanstallning.kallelsen.ej_behandlade.length" data-testid="kallelsen-mot-protokollet">
          <h3>Kallelsen mot protokollet</h3>
          <p class="liten">
            {{ n(sammanstallning.kallelsen.ej_behandlade.length, 'punkt', 'punkter') }} i kallelsen behandlades inte:
          </p>
          <ul>
            <li v-for="(p, i) in sammanstallning.kallelsen.ej_behandlade" :key="i" class="liten">
              <a v-if="p.lank" :href="p.lank.url" target="_blank" rel="noopener">{{ p.rubrik ?? p.text }}</a>
              <template v-else>{{ p.rubrik ?? p.text }}</template>
              <template v-if="p.lank?.sida"> (sidan {{ p.lank.sida }} i kallelsen)</template>
            </li>
          </ul>
        </div>
      </div>
    </template>
  </section>
</template>

<style scoped>
.kort {
  background: var(--surface);
  border: 1px solid var(--line);
  border-radius: var(--radius);
  padding: 24px;
  margin-bottom: 24px;
}
.huvud {
  display: flex;
  flex-wrap: wrap;
  gap: 8px 12px;
  align-items: baseline;
  margin-bottom: 12px;
}
.huvud h2 {
  margin: 0;
}
.ingen {
  margin: 0;
  color: var(--ink-secondary);
}
.huvudtal {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 12px;
  margin-bottom: 12px;
}
.tal {
  display: grid;
  gap: 2px;
  padding: 10px 12px;
  text-align: left;
  font: inherit;
  color: var(--ink);
  background: var(--page);
  border: 1px solid transparent;
  border-radius: var(--radius);
  cursor: pointer;
}
.tal:hover,
.tal[aria-pressed='true'] {
  border-color: var(--accent);
}
.tal .v {
  font-size: 32px;
  font-weight: 600;
  line-height: 1.1;
}
.tal .e {
  font-size: 12px;
  color: var(--ink-secondary);
}
.rad {
  display: flex;
  flex-wrap: wrap;
  align-items: baseline;
  gap: 6px 16px;
  padding: 8px 0;
  border-top: 1px solid var(--line);
  font-size: 13px;
}
.radrubrik {
  min-width: 96px;
  font-weight: 600;
  color: var(--ink-secondary);
}
.enigt,
.noll {
  color: var(--ink-muted);
}
.lank {
  padding: 0;
  font: inherit;
  color: var(--ink);
  background: none;
  border: 0;
  border-bottom: 1px dotted var(--line-strong);
  cursor: pointer;
}
.lank:hover,
.lank[aria-pressed='true'] {
  color: var(--accent);
  border-bottom-color: var(--accent);
}
.lank[aria-pressed='true'] {
  font-weight: 600;
}
.chip {
  padding: 0 6px;
  font: inherit;
  font-size: 11px;
  font-weight: 500;
  line-height: 18px;
  white-space: nowrap;
  border: 1px solid transparent;
  border-radius: var(--radius-mark);
  cursor: pointer;
}
.chip:hover,
.chip[aria-pressed='true'] {
  border-color: currentColor;
}
.votering {
  background: var(--markning-votering);
  color: var(--markning-votering-text);
}
.reservation {
  background: var(--markning-reservation);
  color: var(--markning-reservation-text);
}
.oenighet {
  background: var(--markning-oenighet);
  color: var(--markning-oenighet-text);
}
.vidare {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 16px;
  padding-top: 12px;
  border-top: 1px solid var(--line);
}
.vidare h3 {
  font-size: 13px;
  margin: 0 0 4px;
}
.vidare ul {
  margin: 0 0 8px;
  padding-left: 18px;
  font-size: 13px;
}
.vidare a {
  color: var(--accent);
}
.liten {
  margin: 0 0 4px;
  font-size: 12px;
  color: var(--ink-secondary);
}
a.liten {
  color: var(--accent);
}
@media (max-width: 760px) {
  .huvudtal {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
  .vidare {
    grid-template-columns: 1fr;
  }
}
</style>
