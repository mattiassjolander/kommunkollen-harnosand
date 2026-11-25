<script setup lang="ts">
import type { Motstridighet, Stalle } from '../api'
import { datum } from '../format'

// En motstridighet i styrande dokument (#151). Den är redaktionens analys och står därför med streckad kantlinje och
// etiketten Analys, aldrig i samma stil som fakta (design.md, Säkerhetsmarkeringar). Citaten länkar till sidan i
// plattformens kopia av versionen de kommer från.

defineProps<{ m: Motstridighet; rubrik?: 'h3' | 'h4' }>()

const plats = (s: Stalle) => [s.paragraf, `s. ${s.sida}`].filter(Boolean).join(', ')
</script>

<template>
  <article class="motstridighet" data-testid="motstridighet" :data-typ="m.typ">
    <header class="huvud">
      <component :is="rubrik ?? 'h3'" class="typ">{{ m.typnamn }}</component>
      <span class="analysetikett">Analys</span>
      <span v-if="!m.granskning || m.granskning === 'publicerad'" class="status" data-testid="motstridighetsstatus">
        {{ m.statusdatum ? `${m.statusnamn} ${datum(m.statusdatum)}` : m.statusnamn }}
      </span>
      <span v-if="m.dokument_andrat" class="andrat" data-testid="dokument-andrat">
        Dokumentet har ändrats {{ datum(m.dokument_andrat) }}
      </span>
    </header>

    <p class="forklaring" data-testid="forklaring">{{ m.forklaring }}</p>

    <ul v-if="m.citat.length" class="citat">
      <li v-for="(c, i) in m.citat" :key="i" data-testid="citat">
        <blockquote>”{{ c.text }}”</blockquote>
        <p class="kalla">
          <RouterLink :to="c.lank">{{ c.titel }}</RouterLink>, version {{ c.version }}, {{ plats(c) }} ·
          <a :href="c.kopia" target="_blank" rel="noopener">Sidan i PDF:en</a>
        </p>
      </li>
    </ul>

    <p v-if="m.uppgift" class="uppgift" data-testid="uppgift">
      {{ m.uppgift.text }}
      <span class="kalla">
        (<RouterLink :to="m.uppgift.lank">{{ m.uppgift.titel }}</RouterLink>, version {{ m.uppgift.version }}, s.
        {{ m.uppgift.sida }} · <a :href="m.uppgift.kopia" target="_blank" rel="noopener">Sidan i PDF:en</a>)
      </span>
    </p>

    <p v-if="m.typ === 'flera_versioner'" class="dokument" data-testid="berorda">
      Dokumenten:
      <template v-for="(d, i) in m.dokument" :key="d.id">
        <template v-if="i > 0">{{ i === m.dokument.length - 1 ? ' och ' : ', ' }}</template>
        <RouterLink :to="`/politik/styrande-dokument/${d.id}`">{{ d.titel }}</RouterLink>
      </template>
    </p>

    <p v-if="m.grund" class="not">Förslaget kommer från insamlingen: {{ m.grund }}.</p>
    <p v-if="m.anteckning" class="not" data-testid="anteckning">Anteckning: {{ m.anteckning }}</p>
    <slot />
  </article>
</template>

<style scoped>
.motstridighet {
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
.typ {
  margin: 0;
  font-size: 15px;
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
  border-style: solid;
}
.status {
  font-size: 13px;
  color: var(--ink-secondary);
}
.forklaring {
  margin: 0 0 8px;
  max-width: 70ch;
}
.citat {
  list-style: none;
  margin: 0 0 8px;
  padding: 0;
}
.citat li {
  margin-bottom: 8px;
}
blockquote {
  margin: 0;
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
.uppgift,
.dokument {
  font-size: 13px;
  margin: 0 0 8px;
}
</style>
