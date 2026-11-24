// Visning av rankningar (#66). Texterna beskriver bara siffrorna och värderar inte placeringarna.

const tvadecimaler = new Intl.NumberFormat('sv-SE', { maximumFractionDigits: 2 })
const medtecken = new Intl.NumberFormat('sv-SE', { maximumFractionDigits: 2, signDisplay: 'exceptZero' })

/** Ett värde med högst två decimaler, t.ex. 3.1829 → "3,18". */
export function tal2(v: number | null): string {
  return v === null ? 'Uppgift saknas' : tvadecimaler.format(v)
}

/** Skillnad med tecken, t.ex. 0.12 → "+0,12". */
export function skillnad2(v: number | null): string {
  return v === null ? '–' : medtecken.format(v)
}

/** Förändringen i placeringens nummer mot året före, utan värdering: "Förändring i placering: −18". */
export function rankningsandring(andring: number | null): string {
  if (andring === null) return ''
  return andring === 0 ? 'Samma placering' : `Förändring i placering: ${medtecken.format(andring)}`
}
