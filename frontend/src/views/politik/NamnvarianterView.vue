<script setup lang="ts">
// Namnvarianter (#165): namn med ett mellannamn eller en annan stavning som kan vara samma person. Plattformen slår
// ihop varianter som bara skiljer sig i bindestreck eller mellanslag. Andra skillnader blir förslag, som en redaktör
// bekräftar (namnen slås ihop) eller avvisar (förslaget kommer inte tillbaka), ADR-0002.
import { computed, inject, ref, watch, type Ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import {
  avvisaNamnforslag,
  bekraftaNamnforslag,
  EjInloggad,
  hamtaNamnforslag,
  type Jag,
  type Namnforslag,
  type Namnforslagsstatus,
} from '../../api'
import { datumTid, sammantradesdatum } from '../../format'
import Partimarkering from '../../components/Partimarkering.vue'

const FLIKAR: { id: Namnforslagsstatus; namn: string }[] = [
  { id: 'forslag', namn: 'Förslag' },
  { id: 'bekraftad', namn: 'Bekräftade' },
  { id: 'avvisad', namn: 'Avvisade' },
]

const route = useRoute()
const router = useRouter()
const utloggad = inject<() => void>('utloggad', () => {})
const jag = inject<Ref<Jag | null>>('jag', ref(null))
const arRedaktor = computed(() => jag.value?.roller.includes('redaktor') ?? false)

const flik = computed<Namnforslagsstatus>(() => {
  const s = route.query.status
  return s === 'bekraftad' || s === 'avvisad' ? s : 'forslag'
})

const forslag = ref<Namnforslag[]>([])
const beslutade = ref<Namnforslag[]>([])
const laddar = ref(true)
const fel = ref<string | null>(null)
const arbetar = ref<number | null>(null)

async function ladda() {
  if (!arRedaktor.value) {
    laddar.value = false
    return
  }
  laddar.value = true
  fel.value = null
  try {
    forslag.value = await hamtaNamnforslag(flik.value)
  } catch (e) {
    if (e instanceof EjInloggad) return utloggad()
    fel.value = e instanceof Error ? e.message : String(e)
  } finally {
    laddar.value = false
  }
}
watch(() => [flik.value, arRedaktor.value], ladda, { immediate: true })

function visa(f: Namnforslagsstatus) {
  beslutade.value = []
  router.push({ query: f === 'forslag' ? {} : { status: f } })
}

async function besluta(f: Namnforslag, bekrafta: boolean) {
  arbetar.value = f.id
  fel.value = null
  try {
    const ny = await (bekrafta ? bekraftaNamnforslag(f.id) : avvisaNamnforslag(f.id))
    // En sammanslagning kan göra andra förslag inaktuella. De försvinner vid nästa tolkning.
    forslag.value = forslag.value.filter((x) => x.id !== f.id)
    beslutade.value = [ny, ...beslutade.value]
  } catch (e) {
    if (e instanceof EjInloggad) return utloggad()
    fel.value = e instanceof Error ? e.message : String(e)
  } finally {
    arbetar.value = null
  }
}

const antalText = computed(() => {
  const n = forslag.value.length
  if (flik.value === 'forslag') return `${n} förslag att granska`
  return `${n} ${flik.value === 'bekraftad' ? 'bekräftade' : 'avvisade'} förslag`
})
</script>

<template>
  <header class="vyhuvud">
    <h1>Namnvarianter</h1>
    <p class="ingress">
      Namn i protokollen som kan vara samma person: samma förnamn och efternamn (eller en liten skillnad i stavningen),
      samma parti, och aldrig i samma närvarolista. Namn som bara skiljer sig i bindestreck eller mellanslag slås ihop
      automatiskt. Bekräfta slår ihop namnen, och namnet som förekommer oftast blir huvudnamn. Ett avvisat förslag
      kommer inte tillbaka. En sammanslagning kan delas upp på ledamotens sida.
    </p>
  </header>

  <p v-if="!arRedaktor" class="saknas">Namnvarianterna visas bara för redaktörer.</p>
  <template v-else>
    <nav class="statusflikar" aria-label="Förslagens status">
      <button
        v-for="f in FLIKAR"
        :key="f.id"
        type="button"
        :class="{ aktiv: flik === f.id }"
        :aria-current="flik === f.id ? 'page' : undefined"
        :data-testid="`flik-${f.id}`"
        @click="visa(f.id)"
      >
        {{ f.namn }}
      </button>
    </nav>

    <p v-if="laddar">Hämtar förslag…</p>
    <template v-else>
      <p v-if="fel" class="fel" role="alert">{{ fel }}</p>
      <p class="antal" data-testid="antal-forslag">{{ antalText }}</p>

      <ul class="ko" data-testid="namnforslag">
        <li v-for="f in forslag" :key="f.id" class="kort" data-testid="namnforslag-kort">
          <div class="par">
            <div v-for="(n, i) in f.namn" :key="i" class="sida">
              <p class="namn">
                <RouterLink v-if="n.ledamot" :to="`/politik/ledamoter/${n.ledamot.id}`">{{ n.namn }}</RouterLink>
                <template v-else>{{ n.namn }}</template>
              </p>
              <template v-if="n.ledamot">
                <p v-if="n.ledamot.namn !== n.namn || n.ledamot.andra_namn.length" class="anteckning">
                  Personen: {{ [n.ledamot.namn, ...n.ledamot.andra_namn].join(', ') }}
                </p>
                <p class="anteckning">
                  <Partimarkering v-for="p in n.ledamot.partier" :key="p" :parti="p" />
                  {{ n.ledamot.antal_sammantraden }}
                  {{ n.ledamot.antal_sammantraden === 1 ? 'sammanträde' : 'sammanträden' }}
                  · {{ n.ledamot.organ.map((o) => o.namn).join(', ') }}
                  <template v-if="n.ledamot.senast"> · senast {{ sammantradesdatum(n.ledamot.senast) }}</template>
                </p>
              </template>
            </div>
          </div>
          <p class="grund">{{ f.skal }}</p>

          <div v-if="f.status === 'forslag'" class="knappar">
            <button
              type="button"
              class="knapp primar"
              :disabled="arbetar === f.id"
              data-testid="bekrafta"
              @click="besluta(f, true)"
            >
              Slå ihop
            </button>
            <button type="button" class="knapp" :disabled="arbetar === f.id" data-testid="avvisa" @click="besluta(f, false)">
              Avvisa
            </button>
          </div>
          <p v-else-if="f.beslutad_av" class="anteckning" data-testid="beslutsfattare">
            {{ f.status === 'bekraftad' ? 'Bekräftad' : 'Avvisad' }} av {{ f.beslutad_av }},
            {{ f.beslutad ? datumTid(f.beslutad) : '' }}
          </p>
        </li>
      </ul>
      <p v-if="!forslag.length && flik === 'forslag'" class="saknas">Inga förslag att granska.</p>

      <section v-if="beslutade.length" aria-labelledby="besl-rubrik">
        <h2 id="besl-rubrik">Beslutade nu</h2>
        <ul class="lista" data-testid="beslutade">
          <li v-for="f in beslutade" :key="f.id">
            {{ f.namn.map((n) => n.namn).join(' / ') }}: {{ f.status === 'bekraftad' ? 'sammanslagna' : 'avvisat' }}
          </li>
        </ul>
      </section>
    </template>
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
.statusflikar {
  display: flex;
  gap: 4px;
  border-bottom: 1px solid var(--line);
  margin-bottom: 8px;
}
.statusflikar button {
  font: inherit;
  font-size: 13px;
  padding: 6px 12px;
  border: none;
  border-bottom: 2px solid transparent;
  background: none;
  color: var(--ink-secondary);
  cursor: pointer;
}
.statusflikar button.aktiv {
  color: var(--ink);
  font-weight: 600;
  border-bottom-color: var(--accent);
}
.antal,
.anteckning {
  font-size: 13px;
  color: var(--ink-secondary);
}
.anteckning {
  margin: 4px 0 0;
}
.ko {
  list-style: none;
  margin: 0 0 24px;
  padding: 0;
  display: grid;
  gap: 16px;
}
.kort {
  background: var(--surface);
  border: 1px solid var(--line);
  border-radius: var(--radius);
  padding: 20px 24px;
}
.par {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(240px, 1fr));
  gap: 16px;
}
.namn {
  margin: 0;
  font-weight: 600;
}
.grund {
  margin: 12px 0 0;
  font-size: 13px;
}
.knappar {
  display: flex;
  gap: 8px;
  margin-top: 16px;
}
.saknas {
  color: var(--ink-secondary);
}
.fel {
  color: var(--status-critical);
}
</style>
