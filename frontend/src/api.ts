export interface Datakalla {
  id: string
  titel: string
  url: string
}

export interface Matt {
  id: string
  titel: string
  beskrivning: string
  enhet: string
  kallans_publicering: string | null
  datakalla: Datakalla
}

export interface Version {
  varde: number | null
  kallans_publicering: string | null
  /** När plattformen hämtade den här versionen. */
  hamtad: string
  version: number
}

/** Ett värde för en period: aktuell version plus tidigare versioner (kravspec 11.5 och 12.3). */
export interface Punkt extends Version {
  period: string
  senast_hamtad: string
  senast_andrad: string
  reviderad: boolean
  /** Tidigare versioner, senaste först. */
  historik: Version[]
}

/** Det som visas vid ↻: föregående värde (i visningsenheten), när det ändrades och av vilken källa. */
export interface Revision {
  tidigare: number | null
  andrad: string
  kalla: string
}

export interface Serie {
  matt: Matt
  omrade: string
  punkter: Punkt[]
}

/** Kastas när API:t svarar 401. Appen visar då inloggningssidan. */
export class EjInloggad extends Error {}

export interface Jag {
  epost: string
  namn: string
  roller: string[]
}

export interface Inloggningsmetod {
  google: boolean
  test: boolean
  anonym_lasning: boolean
}

export async function hamtaJag(): Promise<Jag | null> {
  const svar = await fetch('/api/auth/jag')
  if (svar.status === 401) return null
  if (!svar.ok) throw new Error(`API-fel ${svar.status}`)
  return svar.json()
}

export async function hamtaInloggningsmetod(): Promise<Inloggningsmetod> {
  const svar = await fetch('/api/auth/metod')
  if (!svar.ok) throw new Error(`API-fel ${svar.status}`)
  return svar.json()
}

export async function testinloggning(roll: string): Promise<void> {
  const svar = await fetch(`/api/auth/test/${roll}`, { method: 'POST' })
  if (!svar.ok) throw new Error(`Testinloggning misslyckades (${svar.status})`)
}

export async function loggaUt(): Promise<void> {
  await fetch('/api/auth/logga-ut', { method: 'POST' })
}

export async function hamtaSerie(mattId: string): Promise<Serie | null> {
  const svar = await fetch(`/api/matt/${encodeURIComponent(mattId)}/serie`)
  if (svar.status === 401) throw new EjInloggad()
  if (svar.status === 404) return null
  if (!svar.ok) throw new Error(`API-fel ${svar.status}`)
  return svar.json()
}

// Uppdateringsstatus (kravspec avsnitt 12)

export type Kallstatus = 'lyckad' | 'inga_nya' | 'delvis_fel' | 'misslyckad'
export type Korningsstatus = 'pagar' | 'lyckad' | 'delvis_fel' | 'misslyckad'

export interface Korning {
  id: number
  utlosare: 'manuell' | 'schema'
  startad: string
  avslutad: string | null
  status: Korningsstatus
}

export interface GlobalStatus {
  senaste_korning: Korning | null
  senaste_lyckade_korning: Korning | null
  kallor_kontrollerade: number
  kallor_utan_fel: number
  fullstandigt_uppdaterad: boolean
  /** null om schemat är avstängt. */
  nasta_korning: string | null
}

export interface Kallstatusrad {
  id: string
  titel: string
  url: string
  senaste_kontroll: string | null
  senaste_lyckade_hamtning: string | null
  senaste_publicering: string | null
  status: Kallstatus | null
  fel: string | null
}

export interface Kallkorning {
  datakalla_id: string
  titel: string
  status: Kallstatus
  antal_nya: number
  antal_andrade: number
  antal_oforandrade: number
  fel: string | null
  senaste_publicering: string | null
  startad: string
  avslutad: string | null
}

export interface Korningslogg extends Korning {
  kallor: Kallkorning[]
}

async function hamta<T>(url: string): Promise<T> {
  const svar = await fetch(url)
  if (svar.status === 401) throw new EjInloggad()
  if (!svar.ok) throw new Error(`API-fel ${svar.status}`)
  return svar.json()
}

export const hamtaStatus = () => hamta<GlobalStatus>('/api/status')
export const hamtaDatakallor = () => hamta<Kallstatusrad[]>('/api/datakallor')
export const hamtaKorningslogg = () => hamta<Korningslogg[]>('/api/insamlingar')

// Ekonomiska nyckeltal (kravspec 3.1 och 3.3)

export interface Nyckeltal {
  id: string
  prisniva: string | null
  /** null om ingen insamling har hämtat måttet än. */
  serie: Serie | null
}

export interface Nyckeltalsgrupp {
  id: string
  titel: string
  nyckeltal: Nyckeltal[]
}

export const hamtaEkonomi = () => hamta<{ omrade: string; grupper: Nyckeltalsgrupp[] }>('/api/ekonomi')
