// Revideringar mellan SKR:s skatteunderlagsprognoser (#161): hur prognosen för ett år ändras från ett cirkulär
// till nästa, och vilka rader i prognosunderlaget som drev ändringen. Beloppen är i tkr som i källan.
import type { Skatteunderlagsprognos } from './api'

/** Raden som värmekartan och raden om budgeten visar: summa intäkter inklusive avräkning och fastighetsavgift. */
export const SUMMARAD = 'summa_inkl'
/** Summarader räknas inte som drivkrafter, de är summor av de andra raderna. */
const SUMMOR = new Set(['summa_intakter', SUMMARAD])

/** Året cirkuläret publicerades. */
export const cirkularAr = (p: Skatteunderlagsprognos) => Number(p.publicerad.slice(0, 4))

/** Budgetåret är nästa kalenderår, så det byter av sig självt den 1 januari. */
export const budgetar = (nu = new Date()) => nu.getFullYear() + 1

/** Värdet i tkr för en rad och ett år, eller null om prognosen inte har året. */
export function varde(p: Skatteunderlagsprognos, rad: string, ar: number): number | null {
  if (!p.ar.includes(ar)) return null
  return p.rader.find((r) => r.id === rad)?.tkr[String(ar)] ?? null
}

export interface Andring {
  tkr: number
  fran: number
  till: number
  /** Ändringen i procent av det tidigare värdet, null när det tidigare värdet är noll. */
  procent: number | null
}

/** Ändringen från ett cirkulär till ett annat, eller null när året saknas i någon av prognoserna. */
export function andring(fran: Skatteunderlagsprognos, till: Skatteunderlagsprognos, rad: string, ar: number): Andring | null {
  const a = varde(fran, rad, ar)
  const b = varde(till, rad, ar)
  if (a === null || b === null) return null
  return { tkr: b - a, fran: a, till: b, procent: a === 0 ? null : ((b - a) / Math.abs(a)) * 100 }
}

export interface Revidering {
  fran: Skatteunderlagsprognos
  till: Skatteunderlagsprognos
}

/** År som har cirkulär, i stigande ordning. */
export const cirkularAren = (prognoser: Skatteunderlagsprognos[]) => [...new Set(prognoser.map(cirkularAr))].sort((a, b) => a - b)

/**
 * Revideringarna för cirkulären från ett år, i ordning: varje cirkulär mot det föregående. Årets första cirkulär
 * jämförs med det sista från året före, om det finns. `prognoser` är sorterade efter publiceringsdatum.
 */
export function revideringar(prognoser: Skatteunderlagsprognos[], ar: number): Revidering[] {
  const ut: Revidering[] = []
  prognoser.forEach((p, i) => {
    if (i > 0 && cirkularAr(p) === ar) ut.push({ fran: prognoser[i - 1], till: p })
  })
  return ut
}

/** Prognosåren som någon av revideringarna har, i stigande ordning. */
export const prognosAren = (rev: Revidering[]) =>
  [...new Set(rev.flatMap((r) => [...r.fran.ar, ...r.till.ar]))].sort((a, b) => a - b)

export interface Drivkraft {
  id: string
  etikett: string
  tkr: number
}

/** Ändringen per rad i prognosunderlaget, utan summaraderna och utan rader som inte ändras (avrundat till 0,0 mnkr). */
export function drivkrafter(fran: Skatteunderlagsprognos, till: Skatteunderlagsprognos, ar: number): Drivkraft[] {
  return till.rader
    .filter((r) => !SUMMOR.has(r.id))
    .map((r) => ({ id: r.id, etikett: r.etikett, tkr: (varde(till, r.id, ar) ?? 0) - (varde(fran, r.id, ar) ?? 0) }))
    .filter((d) => Math.round(d.tkr / 100) !== 0)
}

/** Cirkulären för raden om budgeten: årets första och det senaste, från samma år som det senaste. */
export function budgetjamforelse(prognoser: Skatteunderlagsprognos[]): Revidering | null {
  const till = prognoser.at(-1)
  if (!till) return null
  const fran = prognoser.find((p) => cirkularAr(p) === cirkularAr(till))!
  return { fran, till }
}
