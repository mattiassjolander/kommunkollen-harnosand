<script setup lang="ts">
import type { Process, Processteg } from '../api'
import { datum } from '../format'
import Motstridighetskort from './Motstridighetskort.vue'

// Stegen i en process ur reglementen och delegationsordningar (#152), i ordning: vem, vad, när och källan med länk
// till sidan i plattformens kopia. Processen är redaktionens analys och står därför med streckad kantlinje och
// etiketten Analys (design.md, Säkerhetsmarkeringar). Publicerade motstridigheter som citerar stället ett steg bygger
// på visas vid steget. Sloten `steg` tar redaktionens åtgärder för ett steg.

defineProps<{ p: Process }>()
defineSlots<{ default?: () => unknown; steg?: (props: { s: Processteg }) => unknown }>()
</script>

<template>
  <article class="process" data-testid="process">
    <header class="huvud">
      <span class="analysetikett">Analys</span>
      <span v-if="p.steg.length" class="not">
        {{ p.steg.length === 1 ? '1 steg' : `${p.steg.length} steg` }} ur
        {{ p.dokument.length === 1 ? '1 dokument' : `${p.dokument.length} dokument` }}
      </span>
    </header>
    <p v-if="p.beskrivning" class="beskrivning">{{ p.beskrivning }}</p>
    <p v-if="!p.steg.length" class="not" data-testid="inga-steg">Stegen är inte inlästa än.</p>
    <ol class="steg">
      <li v-for="s in p.steg" :key="s.id" data-testid="steg">
        <p class="vem-vad">
          <strong data-testid="vem">{{ s.vem }}</strong>
          <span data-testid="vad">{{ s.vad }}</span>
        </p>
        <p v-if="s.nar" class="nar" data-testid="nar">{{ s.nar }}</p>
        <span v-if="s.dokument_andrat" class="andrat" data-testid="dokument-andrat">
          Dokumentet har ändrats {{ datum(s.dokument_andrat) }}
        </span>
        <blockquote data-testid="citat">”{{ s.kalla.text }}”</blockquote>
        <p class="kalla" data-testid="kalla">
          <RouterLink :to="s.kalla.lank">{{ s.kalla.titel }}</RouterLink>, version {{ s.kalla.version }},
          {{ s.kalla.paragraf }}, s. {{ s.kalla.sida }} ·
          <a :href="s.kalla.kopia" target="_blank" rel="noopener">Sidan i PDF:en</a>
        </p>
        <div v-if="s.motstridigheter.length" class="vid" data-testid="motstridigheter-vid-steget">
          <p class="not">Motstridighet som rör stället:</p>
          <Motstridighetskort v-for="m in s.motstridigheter" :key="m.id" :m="m" rubrik="h4" />
        </div>
        <slot name="steg" :s="s" />
      </li>
    </ol>
    <slot />
  </article>
</template>

<style scoped>
.process {
  border: 1px dashed var(--line-strong);
  border-radius: var(--radius);
  padding: 16px;
  margin: 0 0 12px;
}
.huvud {
  display: flex;
  flex-wrap: wrap;
  align-items: baseline;
  gap: 8px;
  margin-bottom: 8px;
}
.analysetikett,
.andrat {
  font-size: 12px;
  font-weight: 600;
  color: var(--ink-secondary);
  border: 1px dashed var(--line-strong);
  border-radius: var(--radius);
  padding: 0 6px;
}
.andrat {
  display: inline-block;
  border-style: solid;
  margin: 0 0 4px;
}
.beskrivning {
  margin: 0 0 8px;
  max-width: 70ch;
  color: var(--ink-secondary);
}
.steg {
  margin: 0;
  padding-left: 24px;
}
.steg > li {
  margin-bottom: 16px;
}
.vem-vad {
  margin: 0;
  max-width: 70ch;
}
.vem-vad strong {
  margin-right: 6px;
}
.nar {
  margin: 2px 0 4px;
  font-size: 13px;
  font-weight: 600;
}
blockquote {
  margin: 4px 0 0;
  padding-left: 12px;
  border-left: 2px solid var(--line-strong);
  font-size: 13px;
}
.kalla,
.not {
  font-size: 12px;
  color: var(--ink-muted);
  margin: 2px 0 0;
}
.vid {
  margin-top: 8px;
}
</style>
