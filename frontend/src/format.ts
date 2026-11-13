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
