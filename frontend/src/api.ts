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
export type Korningsstatus = 'pagar' | 'avbruten' | 'lyckad' | 'delvis_fel' | 'misslyckad'

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

/** Kör om insamlingen för en enskild datakälla (redaktör). Returnerar körningens status. */
export async function korOmKalla(kalla: string): Promise<{ status: Korningsstatus }> {
  const svar = await fetch(`/api/insamlingar?kalla=${encodeURIComponent(kalla)}`, { method: 'POST' })
  if (svar.status === 401) throw new EjInloggad()
  if (svar.status === 409) throw new Error('En insamling pågår redan. Försök igen när den är klar.')
  if (!svar.ok) throw new Error(`API-fel ${svar.status}`)
  return svar.json()
}

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

// Ekonomiska flöden – Sankey (kravspec 4)

export interface Kallhanvisning {
  titel: string
  url: string
}

export interface Flodesnod {
  id: string
  titel: string
  sida: 'in' | 'ut' | 'mitt'
  /** tkr */
  belopp: number
  forklaring: string
  kallor: Kallhanvisning[]
}

export interface Flode {
  fran: string
  till: string
  /** tkr */
  belopp: number
  andel: number
  kr_per_invanare: number | null
  kallor: Kallhanvisning[]
  /** Finns när ett jämförelseår är valt och båda åren har fullständigt underlag. */
  jamforelse?: Jamforelse
}

export interface Jamforelse {
  /** Beloppet jämförelseåret (tkr), null om flödet inte fanns då. */
  belopp: number | null
  titel: string | null
  /** tkr */
  forandring: number | null
  /** Andel, t.ex. 0.05 för 5 %. null när jämförelsebeloppet är noll eller saknas. */
  procent: number | null
}

export interface Verksamhet {
  kod: string
  id: string
  titel: string
}

export interface Flodesmodell {
  ar: string | null
  tillgangliga_ar: { ar: string; fullstandig: boolean }[]
  fullstandig: boolean
  saknas: string[]
  flodestyp: 'brutto' | 'netto'
  indelning: string
  prisniva: string
  noder: Flodesnod[]
  floden: Flode[]
  totalt: number | null
  invanare: number | null
  /** null på kommunnivån, annars det verksamhetsområde som fördjupas. */
  verksamhet: Verksamhet | null
  jamforelse_ar?: string
  jamforelse_fullstandig?: boolean
  jamforelse_totalt?: number | null
}

export interface Flodesval {
  ar?: string
  jamfor?: string
  verksamhet?: string
}

export function hamtaFloden(val: Flodesval = {}) {
  const q = new URLSearchParams(Object.entries(val).filter(([, v]) => v) as [string, string][])
  return hamta<Flodesmodell>(`/api/floden${q.size ? `?${q}` : ''}`)
}

// Politik och beslut: sammanträden och behandlingar ur protokollen (automatiskt tolkade uppgifter)

export interface Organ {
  id: string
  namn: string
}

export interface Protokollkalla {
  dokument_id: number
  /** Originalet på kommunens webbplats. */
  url: string
  /** Plattformens egen kopia. */
  kopia: string
  filnamn: string
  /** 'paragrafprotokoll' gäller bara tills hela protokollet publiceras. */
  typ: 'protokoll' | 'paragrafprotokoll'
  version: number
  sha256: string
  storlek: number
  hamtad: string
  tolkad: string
  datakalla: { id: string; titel: string }
}

export interface Sammantradesrad {
  id: number
  organ: Organ
  datum: string | null
  starttid: string | null
  sluttid: string | null
  plats: string | null
  tolkning: 'tolkad' | 'ej_tolkad'
  avvikelser: string[]
  antal_behandlingar: number
  /** Första och sista paragrafen. */
  paragrafer: [number, number] | null
  protokoll: Protokollkalla
}

export interface Person {
  /** Personen i ledamotsregistret. Saknas för övriga närvarande. */
  ledamot_id: number | null
  namn: string
  /** Som protokollet anger det. '-' är partilös, null betyder att protokollet inte anger parti. */
  parti: string | null
  roll: string | null
  kategori: 'beslutande' | 'ej_tjanstgorande' | 'franvarande' | 'ovrig'
  tjanstgor_for: { namn: string; parti: string | null } | null
  /** Paragrafer personen var beslutande vid, om inte alla. */
  paragrafer: number[] | null
  jav: number[]
}

export interface Behandlingsrad {
  paragraf: number
  rubrik: string
  diarienummer: string[]
  beslut: string | null
}

export interface Sammantrade extends Sammantradesrad {
  narvaro: Person[]
  behandlingar: Behandlingsrad[]
}

export interface Behandling extends Behandlingsrad {
  sammantrade: Sammantradesrad
  beslutande: Person[]
  jav: Person[]
  foregaende: number | null
  nasta: number | null
}

export class Saknas extends Error {}

async function hamtaEllerSaknas<T>(url: string): Promise<T> {
  const svar = await fetch(url)
  if (svar.status === 404) throw new Saknas()
  if (svar.status === 401) throw new EjInloggad()
  if (!svar.ok) throw new Error(`API-fel ${svar.status}`)
  return svar.json()
}

export const hamtaOrgan = () => hamta<Organ[]>('/api/organ')
export const hamtaSammantraden = (organ?: string) =>
  hamta<Sammantradesrad[]>(`/api/sammantraden${organ ? `?organ=${encodeURIComponent(organ)}` : ''}`)
export interface Soktraff {
  paragraf: number
  rubrik: string
  diarienummer: string[]
  sammantrade: { id: number; datum: string | null; tolkning: 'tolkad' | 'ej_tolkad'; organ: Organ }
}
export interface Sokresultat {
  /** Antal träffar totalt. Högst 200 skickas. */
  antal: number
  traffar: Soktraff[]
}
export const sokBehandlingar = (q: string, organ?: string, ar?: string) => {
  const p = new URLSearchParams({ q })
  if (organ) p.set('organ', organ)
  if (ar) p.set('ar', ar)
  return hamta<Sokresultat>(`/api/behandlingar?${p}`)
}
export const hamtaSammantrade = (id: number | string) => hamtaEllerSaknas<Sammantrade>(`/api/sammantraden/${id}`)
export const hamtaBehandling = (id: number | string, paragraf: number | string) =>
  hamtaEllerSaknas<Behandling>(`/api/sammantraden/${id}/behandlingar/${paragraf}`)

// Ledamotsregistret (#30)

export interface Ledamotsrad {
  id: number
  namn: string
  /** Andra namn som en redaktör slagit ihop med personen. */
  andra_namn: string[]
  /** Partiet enligt det senaste protokollet. */
  parti: string | null
  partier: string[]
  organ: Organ[]
  antal_sammantraden: number
  senast: string | null
}

export interface Ledamot {
  id: number
  namn: string
  /** Satt när adressen gällde ett namn som slagits ihop med personen. */
  sammanslagen_med: number | null
  namn_varianter: { id: number; namn: string; huvudnamn: boolean; antal: number }[]
  partier_over_tid: { parti: string | null; fran: string | null; till: string | null; antal: number }[]
  organ: {
    organ: Organ
    roller: string[]
    antal: number
    fran: string | null
    till: string | null
    beslutande: number
    ej_tjanstgorande: number
    franvarande: number
  }[]
  sammantraden: {
    sammantrade: { id: number; datum: string | null; starttid: string | null; organ: Organ; tolkning: string }
    namn: string
    parti: string | null
    roll: string | null
    kategori: 'beslutande' | 'ej_tjanstgorande' | 'franvarande'
    tjanstgor_for: { namn: string; parti: string | null } | null
    paragrafer: number[] | null
    jav: number[]
  }[]
}

export const hamtaLedamoter = () => hamta<Ledamotsrad[]>('/api/ledamoter')
export const hamtaLedamot = (id: number | string) => hamtaEllerSaknas<Ledamot>(`/api/ledamoter/${id}`)

async function skrivLedamot(url: string): Promise<Ledamot> {
  const svar = await fetch(url, { method: 'POST' })
  if (svar.status === 401) throw new EjInloggad()
  if (svar.status === 403) throw new Error('Kräver rollen redaktör.')
  if (!svar.ok) throw new Error((await svar.json().catch(() => null))?.detail ?? `API-fel ${svar.status}`)
  return svar.json()
}
export const slaIhopLedamoter = (huvud: number, med: number) =>
  skrivLedamot(`/api/ledamoter/${huvud}/sammanslagningar?med=${med}`)
export const delaUppLedamot = (namnId: number) => skrivLedamot(`/api/ledamoter/${namnId}/uppdelning`)
