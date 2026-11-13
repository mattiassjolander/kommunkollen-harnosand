// Svenskt talformat: mellanslag som tusentalsavgränsare, komma som decimaltecken.

const heltal = new Intl.NumberFormat('sv-SE', { maximumFractionDigits: 0 })

export function tal(v: number | null, enhet = ''): string {
  if (v === null) return 'Uppgift saknas'
  return enhet ? `${heltal.format(v)} ${enhet}` : heltal.format(v)
}

const lopdatum = new Intl.DateTimeFormat('sv-SE', { day: 'numeric', month: 'short', year: 'numeric' })

/** "15 nov. 2026" → "15 nov 2026" (designprofilens löptextformat). */
export function datum(iso: string | null): string {
  if (!iso) return 'okänt'
  return lopdatum.format(new Date(iso)).replace('.', '')
}

const klockslag = new Intl.DateTimeFormat('sv-SE', { hour: '2-digit', minute: '2-digit' })

/** Löptext med klockslag: "13 nov 2026, 14:02". */
export function datumTid(iso: string | null): string {
  if (!iso) return 'aldrig'
  return `${datum(iso)}, ${klockslag.format(new Date(iso))}`
}

const tabelldag = new Intl.DateTimeFormat('sv-SE', { year: 'numeric', month: '2-digit', day: '2-digit' })

/** Tabellformat: "2026-11-13 14:02", eller bara "2026-08-28" för ett datum utan tid. */
export function tabelldatum(iso: string | null): string {
  if (!iso) return '–'
  if (/^\d{4}-\d{2}-\d{2}$/.test(iso)) return iso
  const d = new Date(iso)
  return `${tabelldag.format(d)} ${klockslag.format(d)}`
}
