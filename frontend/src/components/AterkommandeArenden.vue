<script setup lang="ts">
// Återkommande ärenden (#46): ärenden som behandlats vid flera sammanträden, flest först.
// Återremisser och bordläggningar visas för sig, eftersom de förklarar varför ärendet återkommer.
import { computed, ref } from 'vue'
import type { Aterkommande } from '../api'
import { sammantradesdatum, tal } from '../format'

const props = defineProps<{ a: Aterkommande }>()
const SIDA = 25
const antal = ref(SIDA)
const visade = computed(() => props.a.arenden.slice(0, antal.value))
const HANDELSE = { aterremiss: 'Återremiss', bordlaggning: 'Bordläggning' } as const
</script>

<template>
  <section class="kort" aria-labelledby="aterkommande-rubrik" data-testid="aterkommande">
    <h2 id="aterkommande-rubrik">Återkommande ärenden</h2>
    <p class="forklaring">
      Ärenden som behandlats vid flera sammanträden under perioden, till exempel i en nämnd, kommunstyrelsen och
      fullmäktige. Stående punkter som val av justerare och informationsärenden räknas inte.
    </p>
    <div class="nyckeltal">
      <div class="tal"><span class="varde" data-testid="antal-aterkommande">{{ tal(a.summa.arenden) }}</span><span class="etikett">Återkommande ärenden</span></div>
      <div class="tal"><span class="varde">{{ tal(a.summa.aterremisser) }}</span><span class="etikett">Återremisser</span></div>
      <div class="tal"><span class="varde">{{ tal(a.summa.bordlaggningar) }}</span><span class="etikett">Bordläggningar</span></div>
    </div>
    <p v-if="!a.arenden.length" class="saknas">Inga återkommande ärenden för perioden.</p>
    <div v-else class="rulla">
      <table class="tabell">
        <thead>
          <tr>
            <th scope="col">Ärende</th>
            <th scope="col" class="num">Behandlingar</th>
            <th scope="col" class="num">Återremisser</th>
            <th scope="col" class="num">Bordläggningar</th>
            <th scope="col">Behandlat</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="x in visade" :key="x.id" data-testid="aterkommande-arende">
            <td class="rubrik">
              <RouterLink :to="`/politik/arenden/${x.id}`">{{ x.rubrik }}</RouterLink>
              <span v-if="x.foreslagna_kopplingar" class="forslag" title="Kopplingar som en redaktör ännu inte bekräftat">
                ≈ {{ x.foreslagna_kopplingar }} föreslagen koppling{{ x.foreslagna_kopplingar > 1 ? 'ar' : '' }}
              </span>
            </td>
            <td class="num">{{ tal(x.antal_behandlingar) }}</td>
            <td class="num">{{ tal(x.aterremisser) }}</td>
            <td class="num">{{ tal(x.bordlaggningar) }}</td>
            <td>
              <ul class="behandlingar">
                <li v-for="b in x.behandlingar" :key="`${b.sammantrade.id}-${b.paragraf}`">
                  <RouterLink :to="`/politik/sammantraden/${b.sammantrade.id}/paragraf/${b.paragraf}`">
                    {{ b.sammantrade.organ.namn }} {{ sammantradesdatum(b.sammantrade.datum) }}
                  </RouterLink>
                  <span v-if="b.handelse" class="handelse">{{ HANDELSE[b.handelse] }}</span>
                </li>
              </ul>
            </td>
          </tr>
        </tbody>
      </table>
      <button v-if="antal < a.arenden.length" type="button" class="mer" data-testid="visa-fler" @click="antal += SIDA">
        Visa fler ({{ tal(a.arenden.length - antal) }} kvar)
      </button>
    </div>
  </section>
</template>

<style scoped>
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
  grid-template-columns: repeat(auto-fit, minmax(140px, 1fr));
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
}
.tabell {
  border-collapse: collapse;
  width: 100%;
  font-size: 13px;
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
}
.rubrik {
  min-width: 240px;
}
.forslag {
  display: block;
  font-size: 12px;
  font-style: italic;
  color: var(--ink-secondary);
}
.behandlingar {
  list-style: none;
  padding: 0;
  margin: 0;
  white-space: nowrap;
}
.handelse {
  margin-left: 6px;
  font-size: 12px;
  color: var(--ink-secondary);
  border: 1px solid var(--line-strong);
  border-radius: var(--radius);
  padding: 0 4px;
}
.mer {
  margin-top: 12px;
  font: inherit;
  font-size: 13px;
  color: var(--accent);
  background: none;
  border: 1px solid var(--line);
  border-radius: var(--radius);
  padding: 4px 10px;
  cursor: pointer;
}
.saknas {
  color: var(--ink-muted);
  font-style: italic;
}
a {
  color: var(--accent);
}
</style>
