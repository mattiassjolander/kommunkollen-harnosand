<script setup lang="ts">
// Vänsternavigeringens länklista (#146): huvudvyerna, och undervyerna till den huvudvy man är i.
// Redaktion står sist, avskild med en linje, och bara för redaktör och utgivare.
import { computed } from 'vue'
import { useRoute } from 'vue-router'
import { plats, synligaVyer, type Huvudvy, type Undervy } from '../navigering'

const props = defineProps<{ roller: readonly string[]; vantar: Partial<Record<'rattelser' | 'kopplingar', number>> }>()
const emit = defineEmits<{ valt: [] }>()

const route = useRoute()
const vyer = computed(() => synligaVyer(props.roller))
const har = computed(() => plats(route.path))

const oppen = (h: Huvudvy) => har.value?.huvudvy.till === h.till
const vald = (u: Undervy) => har.value?.undervy?.till === u.till
// En huvudvy med undervyer leder till den första undervyn man får se.
const mal = (h: Huvudvy) => h.undervyer?.[0]?.till ?? h.till

/** Undervyerna i ordning, med grupprubrik före den första i varje grupp. */
function rader(h: Huvudvy): { u: Undervy; grupp: string | null }[] {
  return (h.undervyer ?? []).map((u, i, alla) => ({ u, grupp: u.grupp && u.grupp !== alla[i - 1]?.grupp ? u.grupp : null }))
}
</script>

<template>
  <nav aria-label="Huvudvyer" class="huvudnav">
    <ul>
      <li v-for="h in vyer" :key="h.till" :class="{ redaktion: h.till === '/redaktion' }">
        <RouterLink
          :to="mal(h)"
          class="navlank"
          :class="{ aktiv: oppen(h) }"
          :aria-current="oppen(h) && !h.undervyer ? 'page' : undefined"
          :aria-expanded="h.undervyer ? oppen(h) : undefined"
          @click="emit('valt')"
        >
          {{ h.namn }}
        </RouterLink>
        <ul v-if="h.undervyer && oppen(h)" class="undervyer" :aria-label="h.namn">
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
.navlank {
  display: block;
  padding: 8px 12px;
  border-radius: var(--radius);
  color: var(--ink-secondary);
  text-decoration: none;
}
.navlank:hover,
.underlank:hover {
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
.redaktion {
  margin-top: 12px;
  padding-top: 12px;
  border-top: 1px solid var(--line);
}
</style>
