<script setup lang="ts">
// Vänsternavigeringens länklista (#146, #160): huvudvyerna, och undervyerna till de grupper som är utfällda.
// En grupp med undervyer har en pil som fäller ut eller in gruppen utan att byta sida. Den grupp man är i är alltid
// utfälld. Om Kommunkollen står diskret längre ner, och Redaktion står sist, avskild med en linje, och bara för
// redaktör och utgivare.
import { computed, ref } from 'vue'
import { useRoute } from 'vue-router'
import { plats, synligaVyer, type Huvudvy, type Undervy } from '../navigering'

const props = defineProps<{ roller: readonly string[]; vantar: Partial<Record<'rattelser' | 'kopplingar' | 'namnvarianter', number>> }>()
const emit = defineEmits<{ valt: [] }>()

const route = useRoute()
const vyer = computed(() => synligaVyer(props.roller))
const har = computed(() => plats(route.path))

/** Grupper som läsaren har fällt ut med pilen. */
const utfallda = ref(new Set<string>())

const aktuell = (h: Huvudvy) => har.value?.huvudvy.till === h.till
const oppen = (h: Huvudvy) => aktuell(h) || utfallda.value.has(h.till)
const vald = (u: Undervy) => har.value?.undervy?.till === u.till
// En huvudvy med undervyer leder till den första undervyn man får se.
const mal = (h: Huvudvy) => h.undervyer?.[0]?.till ?? h.till
const listId = (h: Huvudvy) => `undervyer-${h.till.replace(/\W+/g, '') || 'start'}`

function vaxla(h: Huvudvy) {
  if (aktuell(h)) return
  const ny = new Set(utfallda.value)
  if (!ny.delete(h.till)) ny.add(h.till)
  utfallda.value = ny
}

/** Undervyerna i ordning, med grupprubrik före den första i varje grupp. */
function rader(h: Huvudvy): { u: Undervy; grupp: string | null }[] {
  return (h.undervyer ?? []).map((u, i, alla) => ({ u, grupp: u.grupp && u.grupp !== alla[i - 1]?.grupp ? u.grupp : null }))
}
</script>

<template>
  <nav aria-label="Huvudvyer" class="huvudnav">
    <ul>
      <li v-for="h in vyer" :key="h.till" :class="{ redaktion: h.till === '/redaktion', diskret: h.diskret }">
        <div class="rad">
          <RouterLink
            :to="mal(h)"
            class="navlank"
            :class="{ aktiv: aktuell(h) }"
            :aria-current="aktuell(h) && !h.undervyer ? 'page' : undefined"
            @click="emit('valt')"
          >
            {{ h.namn }}
          </RouterLink>
          <button
            v-if="h.undervyer"
            type="button"
            class="pil"
            :aria-label="`Undervyer till ${h.namn}`"
            :aria-expanded="oppen(h)"
            :aria-controls="listId(h)"
            :aria-disabled="aktuell(h) || undefined"
            :title="aktuell(h) ? 'Du är i den här gruppen' : undefined"
            @click="vaxla(h)"
          >
            <span aria-hidden="true">{{ oppen(h) ? '▾' : '▸' }}</span>
          </button>
        </div>
        <ul v-if="h.undervyer" v-show="oppen(h)" :id="listId(h)" class="undervyer" :aria-label="h.namn">
          <template v-for="{ u, grupp } in rader(h)" :key="u.till">
            <li v-if="grupp" class="grupp" aria-hidden="true">{{ grupp }}</li>
            <li>
              <RouterLink
                :to="u.till"
                class="underlank"
                :class="{ aktiv: vald(u) }"
                :aria-current="vald(u) ? 'page' : undefined"
                @click="emit('valt')"
              >
                <span>{{ u.namn }}</span>
                <span v-if="u.vantar && vantar[u.vantar]" class="antal" :aria-label="`${vantar[u.vantar]} väntar`">{{
                  vantar[u.vantar]
                }}</span>
              </RouterLink>
            </li>
          </template>
        </ul>
      </li>
    </ul>
  </nav>
</template>

<style scoped>
ul {
  list-style: none;
  margin: 0;
  padding: 0;
}
.rad {
  display: flex;
  align-items: center;
  gap: 4px;
}
.navlank {
  flex: 1;
  display: block;
  padding: 8px 12px;
  border-radius: var(--radius);
  color: var(--ink-secondary);
  text-decoration: none;
}
.navlank:hover,
.underlank:hover,
.pil:hover:not([aria-disabled='true']) {
  background: var(--accent-wash);
  color: var(--ink);
}
.navlank.aktiv {
  color: var(--ink);
  font-weight: 600;
}
/* En huvudvy utan undervyer markeras som vald, en med undervyer markerar i stället undervyn. */
.navlank.aktiv[aria-current='page'] {
  background: var(--accent-wash);
  color: var(--accent);
}
.pil {
  flex: none;
  width: 32px;
  height: 32px;
  padding: 0;
  border: 0;
  border-radius: var(--radius);
  background: none;
  color: var(--ink-secondary);
  font: inherit;
  font-size: 14px;
  line-height: 1;
  cursor: pointer;
}
.pil[aria-disabled='true'] {
  cursor: default;
}
.pil:focus-visible,
.navlank:focus-visible,
.underlank:focus-visible {
  outline: 2px solid var(--accent);
  outline-offset: -2px;
}
.undervyer {
  margin: 2px 0 8px;
}
.underlank {
  display: flex;
  justify-content: space-between;
  gap: 8px;
  padding: 5px 12px 5px 24px;
  border-radius: var(--radius);
  color: var(--ink-secondary);
  text-decoration: none;
  font-size: 14px;
}
.underlank.aktiv {
  background: var(--accent-wash);
  color: var(--accent);
  font-weight: 600;
}
.grupp {
  padding: 8px 12px 2px 24px;
  font-size: 12px;
  color: var(--ink-muted);
}
.antal {
  font-size: 12px;
  font-variant-numeric: tabular-nums;
  color: var(--ink-secondary);
}
/* Om Kommunkollen: en diskret rad längre ner, skild från huvudvyerna. */
.diskret {
  margin-top: 16px;
}
.diskret .navlank {
  padding-top: 4px;
  padding-bottom: 4px;
  font-size: 14px;
}
.diskret .pil {
  height: 26px;
}
.redaktion {
  margin-top: 12px;
  padding-top: 12px;
  border-top: 1px solid var(--line);
}
</style>
