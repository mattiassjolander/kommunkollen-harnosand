import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import { useRoute } from 'vue-router'
import { arTemanamn, skapaTema, svenskDagFor, temaFor, type Tema } from './hogtider'

/*
 * Vilket högtidstema som visas (docs/design.md, Högtidsteman).
 * - ?tema=<namn> förhandsvisar ett tema oavsett datum, ?tema=inget stänger av det.
 * - ?datum=ÅÅÅÅ-MM-DD räknar temat för en annan dag, t.ex. ?tema=nedrakning&datum=2026-03-01.
 * - "Visa inte teman" i sidfoten sparas i webbläsaren. Går lagringen inte att nå visas teman som vanligt.
 */
const NYCKEL = 'kommunkollen-hogtidsteman'

function lasVisa(): boolean {
  try {
    return localStorage.getItem(NYCKEL) !== 'av'
  } catch {
    return true
  }
}

const visaTeman = ref(lasVisa())
const nu = ref(new Date())

export function sattVisaTeman(visa: boolean) {
  visaTeman.value = visa
  try {
    if (visa) localStorage.removeItem(NYCKEL)
    else localStorage.setItem(NYCKEL, 'av')
  } catch {
    // Valet gäller då bara tills sidan laddas om.
  }
}

function giltigtDatum(v: unknown): string | null {
  return typeof v === 'string' && /^\d{4}-\d{2}-\d{2}$/.test(v) && !Number.isNaN(Date.parse(v)) ? v : null
}

export function useHogtidstema() {
  const route = useRoute()

  const tema = computed<Tema | null>(() => {
    const forhand = route.query.tema
    const datum = giltigtDatum(route.query.datum) ?? nu.value
    if (forhand === 'inget') return null
    if (arTemanamn(forhand)) return skapaTema(forhand, svenskDagFor(datum))
    if (!visaTeman.value) return null
    return temaFor(datum)
  })

  // Temat byts vid midnatt även om sidan står öppen.
  let timer: ReturnType<typeof setInterval> | undefined
  onMounted(() => {
    timer = setInterval(() => (nu.value = new Date()), 10 * 60_000)
  })
  onBeforeUnmount(() => clearInterval(timer))

  return { tema, visaTeman, sattVisaTeman }
}
