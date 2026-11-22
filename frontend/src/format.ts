import { BEHANDLINGSTYPER } from './api'

// Svenskt talformat: mellanslag som tusentalsavgränsare, komma som decimaltecken.

const heltal = new Intl.NumberFormat('sv-SE', { maximumFractionDigits: 0 })
const endecimal = new Intl.NumberFormat('sv-SE', { minimumFractionDigits: 1, maximumFractionDigits: 1 })

/** Procent och miljoner kronor visas med en decimal, övrigt i heltal. */
function decimaler(enhet: string): Intl.NumberFormat {
  return enhet.includes('%') || enhet === 'mnkr' ? endecimal : heltal
}

export function tal(v: number | null, enhet = ''): string {
  if (v === null) return 'Uppgift saknas'
  const s = decimaler(enhet).format(v)
  return enhet ? `${s} ${enhet}` : s
}

/** Axeletikett: decimaler bara när stegen är mindre än ett. */
export function axeltal(v: number, steg: number): string {
  return (steg < 1 ? endecimal : heltal).format(v)
}

/** Belopp i tkr visas i mnkr. Källans värde lagras oförändrat, bara visningen skalas. */
export function visningsskala(enhet: string): { enhet: string; faktor: number } {
  return enhet === 'tkr' ? { enhet: 'mnkr', faktor: 1 / 1000 } : { enhet, faktor: 1 }
}

// Alla tider visas i svensk tid, oavsett var läsaren befinner sig.
const TZ = 'Europe/Stockholm'

const lopdatum = new Intl.DateTimeFormat('sv-SE', { day: 'numeric', month: 'short', year: 'numeric', timeZone: TZ })

/** "15 nov. 2026" → "15 nov 2026" (designprofilens löptextformat). */
export function datum(iso: string | null): string {
  if (!iso) return 'okänt'
  return lopdatum.format(new Date(iso)).replace('.', '')
}

const klockslag = new Intl.DateTimeFormat('sv-SE', { hour: '2-digit', minute: '2-digit', timeZone: TZ })

/** Löptext med klockslag: "13 nov 2026, 14:02". */
export function datumTid(iso: string | null): string {
  if (!iso) return 'aldrig'
  return `${datum(iso)}, ${klockslag.format(new Date(iso))}`
}

const tabelldag = new Intl.DateTimeFormat('sv-SE', { year: 'numeric', month: '2-digit', day: '2-digit', timeZone: TZ })

/** Tabellformat: "2026-11-13 14:02", eller bara "2026-08-28" för ett datum utan tid. */
export function tabelldatum(iso: string | null): string {
  if (!iso) return '–'
  if (/^\d{4}-\d{2}-\d{2}$/.test(iso)) return iso
  const d = new Date(iso)
  return `${tabelldag.format(d)} ${klockslag.format(d)}`
}

/** Talet utan enhet men med enhetens antal decimaler (för tabellceller där enheten står i rubriken). */
export function siffra(v: number | null, enhet: string): string {
  if (v === null) return 'Uppgift saknas'
  return decimaler(enhet).format(v)
}

const forandringsprocent = new Intl.NumberFormat('sv-SE', {
  minimumFractionDigits: 1,
  maximumFractionDigits: 1,
  signDisplay: 'exceptZero',
})

/** Förändring som andel, t.ex. 0.053 → "+5,3 %". */
export function procentforandring(andel: number | null): string {
  if (andel === null) return '–'
  return `${forandringsprocent.format(andel * 100)} %`
}

/** Förändring med tecken i given enhet, t.ex. "+45,2 mnkr". */
export function talforandring(v: number | null, enhet: string): string {
  if (v === null) return 'Uppgift saknas'
  const s = tal(v, enhet)
  return v > 0 ? `+${s}` : s
}

/** Partiet som protokollet anger det: förkortningen, "partilös" för (-), eller att det inte anges. */
export function parti(p: string | null): string {
  if (p === null) return 'parti anges inte i protokollet'
  if (p === '-') return 'partilös'
  return p
}

/** "Monica Fahlén (S)", "Carl-Fredrik Edgren (partilös)". */
export function namnOchParti(namn: string, p: string | null): string {
  return `${namn} (${parti(p)})`
}

/** [121, 122, 123, 125] → "§§ 121–123, 125". */
export function paragraftext(nummer: number[]): string {
  const delar: string[] = []
  let start = nummer[0]
  for (let i = 1; i <= nummer.length; i++) {
    if (nummer[i] !== nummer[i - 1] + 1) {
      const slut = nummer[i - 1]
      delar.push(start === slut ? `${start}` : `${start}–${slut}`)
      start = nummer[i]
    }
  }
  return `${nummer.length > 1 ? '§§' : '§'} ${delar.join(', ')}`
}

const veckodagsdatum = new Intl.DateTimeFormat('sv-SE', { weekday: 'long', day: 'numeric', month: 'long', year: 'numeric', timeZone: TZ })

/** "måndag 28 september 2026" för ett sammanträdesdatum (YYYY-MM-DD). */
export function sammantradesdatum(iso: string | null): string {
  if (!iso) return 'Datum okänt'
  return veckodagsdatum.format(new Date(`${iso}T12:00:00Z`))
}

const ROST = { ja: 'Ja', nej: 'Nej', avstar: 'Avstår', franvarande: 'Frånvarande' } as const

/** Rösten som voteringslistan anger den. */
export function rosttext(r: keyof typeof ROST): string {
  return ROST[r]
}

/** Motionärerna som text: "Monica Fahlén (S), partiet V". */
export function motionarstext(m: { namn: string | null; parti: string | null }[]): string {
  return m.map((p) => (p.namn ? (p.parti ? `${p.namn} (${p.parti})` : p.namn) : `partiet ${p.parti}`)).join(', ')
}

// Rättelser (#33, #74): vad en rättelse rättar och värdena före och efter, som text.
const RATTAT_FALT: Record<string, string> = {
  rubrik: 'Rubrik', beslut: 'Beslut', diarienummer: 'Diarienummer', typ: 'Typ', rost: 'Röst', parti: 'Parti',
  motionarer: 'Motionärer',
}

export function rattelseuppgift(r: { objekt: string; falt: string; namn: string | null; votering: number | null }): string {
  if (r.objekt === 'rost') return `${RATTAT_FALT[r.falt]} för ${r.namn}, votering ${r.votering}`
  if (r.objekt === 'narvaro') return `Parti för ${r.namn} i närvarolistan`
  return RATTAT_FALT[r.falt]
}

export function rattelsevarde(falt: string, v: unknown): string {
  if (v === null || v === undefined || (Array.isArray(v) && !v.length)) {
    return falt === 'parti' ? 'inget parti' : falt === 'typ' ? 'kunde inte klassas' : 'inget'
  }
  if (falt === 'motionarer') return motionarstext(v as { namn: string | null; parti: string | null }[])
  if (falt === 'parti') return parti(v as string)
  if (falt === 'rost') return rosttext(v as keyof typeof ROST)
  if (falt === 'typ') return BEHANDLINGSTYPER.find((t) => t.id === v)?.namn ?? String(v)
  return Array.isArray(v) ? v.join(', ') : String(v)
}
