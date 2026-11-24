/*
 * Högtidsteman (docs/design.md, Högtidsteman). Ren datumlogik utan beroenden till Vue eller webbläsaren,
 * så att den kan testas direkt. Alla datum räknas i svensk tid (Europe/Stockholm).
 */

export type Temanamn =
  | 'nyar'
  | 'pask'
  | 'nationaldagen'
  | 'midsommar'
  | 'valdagen'
  | 'harnosandsdag'
  | 'lucia'
  | 'jul'
  | 'nedrakning'

/** Symbolen vid logotypen. Nedräkningen har ingen symbol. */
export type Temasymbol = 'gnistor' | 'agg' | 'flagga' | 'blomkrans' | 'valsedel' | 'vagen' | 'ljus' | 'stjarnan'

export interface Tema {
  namn: Temanamn
  /** Raden i sidhuvudet. */
  text: string
  symbol: Temasymbol | null
  /** Tooltip med källa, bara på Härnösands dag. */
  tooltip?: string
  lank?: { href: string; text: string }
}

/** Ett kalenderdatum utan tid. Månad 1–12. */
export interface Dag {
  ar: number
  manad: number
  dag: number
}

export const STADSPRIVILEGIER_AR = 1585
export const HARNOSANDS_DAG = { manad: 3, dag: 11 }
export const NEDRAKNING_DAGAR = 30
export const HARNOSANDS_DAG_KALLA =
  'Den 11 mars 1585 fick Härnösand sina stadsprivilegier av Johan III. Det är den dag som brukar firas.'

/** Ordningen avgör krockar: valdagen först, därefter i tabellens ordning (design.md). */
export const TEMAORDNING: Temanamn[] = [
  'valdagen',
  'nyar',
  'pask',
  'nationaldagen',
  'midsommar',
  'harnosandsdag',
  'lucia',
  'jul',
]

const svenskDag = new Intl.DateTimeFormat('en-CA', {
  timeZone: 'Europe/Stockholm',
  year: 'numeric',
  month: '2-digit',
  day: '2-digit',
})

/** Kalenderdagen i Sverige för ett ögonblick, eller ett datum skrivet som ÅÅÅÅ-MM-DD. */
export function svenskDagFor(datum: Date | string): Dag {
  if (typeof datum === 'string') {
    const m = /^(\d{4})-(\d{2})-(\d{2})$/.exec(datum)
    if (!m) throw new Error(`Ogiltigt datum: ${datum}`)
    return { ar: Number(m[1]), manad: Number(m[2]), dag: Number(m[3]) }
  }
  const [ar, manad, dag] = svenskDag.format(datum).split('-').map(Number)
  return { ar, manad, dag }
}

/** Dagnummer räknat i kalenderdagar, så att skottår och sommartid inte spelar in. */
function dagnummer(d: Dag): number {
  return Math.round(Date.UTC(d.ar, d.manad - 1, d.dag) / 86_400_000)
}

function franDagnummer(n: number): Dag {
  const t = new Date(n * 86_400_000)
  return { ar: t.getUTCFullYear(), manad: t.getUTCMonth() + 1, dag: t.getUTCDate() }
}

function veckodag(d: Dag): number {
  // 0 = söndag
  return new Date(Date.UTC(d.ar, d.manad - 1, d.dag)).getUTCDay()
}

/** Påskdagen enligt den gregorianska påskberäkningen (anonym gregoriansk algoritm). */
export function paskdagen(ar: number): Dag {
  const a = ar % 19
  const b = Math.floor(ar / 100)
  const c = ar % 100
  const d = Math.floor(b / 4)
  const e = b % 4
  const f = Math.floor((b + 8) / 25)
  const g = Math.floor((b - f + 1) / 3)
  const h = (19 * a + b - d - g + 15) % 30
  const i = Math.floor(c / 4)
  const k = c % 4
  const l = (32 + 2 * e + 2 * i - h - k) % 7
  const m = Math.floor((a + 11 * h + 22 * l) / 451)
  const manad = Math.floor((h + l - 7 * m + 114) / 31)
  const dag = ((h + l - 7 * m + 114) % 31) + 1
  return { ar, manad, dag }
}

/** Midsommarafton: fredagen 19–25 juni. */
export function midsommarafton(ar: number): Dag {
  for (let dag = 19; dag <= 25; dag++) {
    if (veckodag({ ar, manad: 6, dag }) === 5) return { ar, manad: 6, dag }
  }
  throw new Error('Ingen fredag 19–25 juni')
}

/** Valår för de allmänna valen: vart fjärde år (2022, 2026, 2030 …). */
export function arValar(ar: number): boolean {
  return ar % 4 === 2
}

/** Valdagen: andra söndagen i september valåren, annars null. */
export function valdagen(ar: number): Dag | null {
  if (!arValar(ar)) return null
  let sondagar = 0
  for (let dag = 1; dag <= 14; dag++) {
    if (veckodag({ ar, manad: 9, dag }) === 0 && ++sondagar === 2) return { ar, manad: 9, dag }
  }
  return null
}

function inom(d: Dag, fran: Dag, till: Dag): boolean {
  const n = dagnummer(d)
  return n >= dagnummer(fran) && n <= dagnummer(till)
}

function arSedanPrivilegierna(ar: number): number {
  return ar - STADSPRIVILEGIER_AR
}

/** Om temat gäller den här dagen, och i så fall hur det ser ut. */
function temaOmDetGaller(namn: Temanamn, d: Dag): Tema | null {
  const { ar, manad, dag } = d
  switch (namn) {
    case 'nyar':
      return (manad === 12 && dag === 31) || (manad === 1 && dag === 1) ? skapaTema('nyar', d) : null
    case 'pask': {
      const p = dagnummer(paskdagen(ar))
      return inom(d, franDagnummer(p - 3), franDagnummer(p + 1)) ? skapaTema('pask', d) : null
    }
    case 'nationaldagen':
      return manad === 6 && dag === 6 ? skapaTema('nationaldagen', d) : null
    case 'midsommar': {
      const afton = dagnummer(midsommarafton(ar))
      const n = dagnummer(d)
      return n === afton || n === afton + 1 ? skapaTema('midsommar', d) : null
    }
    case 'valdagen': {
      const v = valdagen(ar)
      return v && dagnummer(v) === dagnummer(d) ? skapaTema('valdagen', d) : null
    }
    case 'harnosandsdag':
      return manad === HARNOSANDS_DAG.manad && dag === HARNOSANDS_DAG.dag ? skapaTema('harnosandsdag', d) : null
    case 'lucia':
      return manad === 12 && dag === 13 ? skapaTema('lucia', d) : null
    case 'jul':
      return manad === 12 && dag >= 24 && dag <= 26 ? skapaTema('jul', d) : null
    case 'nedrakning': {
      const kvar = dagarKvarTillHarnosandsDag(d)
      return kvar >= 1 && kvar <= NEDRAKNING_DAGAR ? skapaTema('nedrakning', d) : null
    }
  }
}

/** Antal kalenderdagar till nästa 11 mars (0 på själva dagen). */
export function dagarKvarTillHarnosandsDag(d: Dag): number {
  const iAr = { ar: d.ar, ...HARNOSANDS_DAG }
  const mal = dagnummer(d) <= dagnummer(iAr) ? iAr : { ar: d.ar + 1, ...HARNOSANDS_DAG }
  return dagnummer(mal) - dagnummer(d)
}

/**
 * Temat med sin text, oavsett om det gäller den här dagen. Används för förhandsvisning (?tema=)
 * och av temaFor. Dagen bestämmer antalet år på Härnösands dag och dagarna i nedräkningen.
 */
export function skapaTema(namn: Temanamn, d: Dag): Tema {
  switch (namn) {
    case 'nyar':
      return { namn, text: 'Gott nytt år', symbol: 'gnistor' }
    case 'pask':
      return { namn, text: 'Glad påsk', symbol: 'agg' }
    case 'nationaldagen':
      return { namn, text: 'Sveriges nationaldag', symbol: 'flagga' }
    case 'midsommar':
      return { namn, text: 'Glad midsommar', symbol: 'blomkrans' }
    case 'valdagen':
      return {
        namn,
        text: 'I dag är det val',
        symbol: 'valsedel',
        lank: { href: 'https://www.val.se/', text: 'val.se' },
      }
    case 'harnosandsdag': {
      const n = arSedanPrivilegierna(d.ar)
      return {
        namn,
        text: `Härnösand fick sina stadsprivilegier i dag för ${n} år sedan (${STADSPRIVILEGIER_AR})`,
        symbol: 'vagen',
        tooltip: HARNOSANDS_DAG_KALLA,
      }
    }
    case 'lucia':
      return { namn, text: 'Glad lucia', symbol: 'ljus' }
    case 'jul':
      return { namn, text: 'God jul', symbol: 'stjarnan' }
    case 'nedrakning': {
      const kvar = dagarKvarTillHarnosandsDag(d)
      const arTill = d.manad > HARNOSANDS_DAG.manad || (d.manad === HARNOSANDS_DAG.manad && d.dag > HARNOSANDS_DAG.dag) ? d.ar + 1 : d.ar
      const n = arSedanPrivilegierna(arTill)
      const text =
        kvar === 1
          ? 'I morgon är det Härnösands dag'
          : `${kvar} dagar kvar till Härnösands dag – ${n} år sedan stadsprivilegierna`
      return { namn, text, symbol: null }
    }
  }
}

/** Temat som gäller en viss dag i svensk tid, eller null. Nedräkningen gäller bara när inget annat tema gör det. */
export function temaFor(datum: Date | string): Tema | null {
  const d = svenskDagFor(datum)
  for (const namn of TEMAORDNING) {
    const t = temaOmDetGaller(namn, d)
    if (t) return t
  }
  return temaOmDetGaller('nedrakning', d)
}

export const TEMANAMN: Temanamn[] = [...TEMAORDNING, 'nedrakning']

export function arTemanamn(v: unknown): v is Temanamn {
  return typeof v === 'string' && (TEMANAMN as string[]).includes(v)
}
