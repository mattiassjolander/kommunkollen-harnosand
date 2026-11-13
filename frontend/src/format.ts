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
