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
  /** Protokollet är en PDF med bara bilder och har lästs med OCR (#52). */
  ocr: boolean
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
  /** Satt när närvarolistan inte anger parti och partiet härletts ur samma eller ett annat protokoll. */
  parti_harlett?: PartiHarlett | null
  /** Publicerade rättelser av partiet. */
  rattelser?: Rattelser
}

export interface PartiHarlett {
  grund: 'samma_protokoll' | 'annat_protokoll'
  /** Sammanträdet partiet hämtades från, när det är ett annat protokoll. */
  sammantrade: { id: number; datum: string | null; organ: Organ } | null
}

export interface Behandlingsrad {
  paragraf: number
  rubrik: string
  diarienummer: string[]
  beslut: string | null
  /** Behandlingstyp, automatiskt klassad ur rubrik och beslut (eller rättad). null = kunde inte klassas. */
  typ?: Behandlingstyp | null
  /** Saknas när behandlingen saknar voteringar respektive reservationer. */
  antal_voteringar?: number
  antal_reservationer?: number
  /** Publicerade rättelser av rubrik, beslut, diarienummer och typ. */
  rattelser?: Rattelser
}

export type Behandlingstyp =
  | 'beslut'
  | 'forslag'
  | 'motion'
  | 'medborgarforslag'
  | 'interpellation'
  | 'information'
  | 'formalia'

/** Behandlingstyperna i visningsordning. Ordningen avgör också färgen i diagram (design.md). */
export const BEHANDLINGSTYPER: { id: Behandlingstyp; namn: string }[] = [
  { id: 'beslut', namn: 'Beslut' },
  { id: 'forslag', namn: 'Förslag till annat organ' },
  { id: 'motion', namn: 'Motion' },
  { id: 'medborgarforslag', namn: 'Medborgarförslag' },
  { id: 'interpellation', namn: 'Interpellation eller fråga' },
  { id: 'information', namn: 'Informationsärende' },
  { id: 'formalia', namn: 'Formalia' },
]

export interface Kortsammantrade {
  id: number
  datum: string | null
  organ: Organ
}

export interface Behandlingsstatistik {
  fran: number
  till: number
  organ: Organ | null
  typer: { id: Behandlingstyp | 'okand'; namn: string }[]
  rader: {
    ar: number
    organ: Organ
    sammantraden: number
    behandlingar: number
    antal: Record<Behandlingstyp | 'okand', number>
  }[]
  summa: { sammantraden: number; behandlingar: number; antal: Record<Behandlingstyp | 'okand', number> }
  underlag: { ej_tolkade: Kortsammantrade[]; paragrafprotokoll: Kortsammantrade[]; utan_datum: number }
  tillgangliga_ar: number[]
}

/** En behandling bakom en siffra i statistiken. */
export interface Statistikbehandling {
  sammantrade: Kortsammantrade
  paragraf: number
  rubrik: string
  diarienummer: string[]
}

export type Motionsutfall = 'bifall' | 'avslag' | 'besvarad' | 'delvis' | 'annat'

export interface Forloppsbehandling {
  sammantrade: Kortsammantrade
  paragraf: number
  rubrik: string
  beslut: string | null
  osaker: boolean
}

export interface Forlopp {
  arende_id: number
  rubrik: string
  vackt: {
    datum: string
    sammantrade_id: number
    paragraf: number
    organ: Organ
    grund: 'beslut' | 'samlingspunkt'
    osaker: boolean
  } | null
  forsta_behandling: Forloppsbehandling
  besvarad: (Forloppsbehandling & { beslut: string | null }) | null
  utfall: Motionsutfall | null
  ledtid_dagar: number | null
  over_ett_ar: boolean
  aterremisser: number
  bordlaggningar: number
  behandlingar: Forloppsbehandling[]
}

export interface Motionsstatistik {
  fran: number
  till: number
  organ: Organ | null
  idag: string
  utfall: { id: Motionsutfall; namn: string }[]
  motioner: {
    per_ar: { ar: number; vackta: number; besvarade: number; utfall: Record<Motionsutfall, number> }[]
    per_parti: { parti: string; vackta: number; besvarade: number; utfall: Record<Motionsutfall, number> }[]
    lista: (Forlopp & { motionarer: { namn: string | null; parti: string | null }[] })[]
    utan_vackt: number
  }
  medborgarforslag: { lista: Forlopp[] }
}

export interface Aterkommande {
  fran: number
  till: number
  organ: Organ | null
  arenden: {
    id: number
    rubrik: string
    antal_behandlingar: number
    aterremisser: number
    bordlaggningar: number
    foreslagna_kopplingar: number
    forsta: string
    senaste: string
    behandlingar: {
      sammantrade: Kortsammantrade
      paragraf: number
      rubrik: string
      handelse: 'aterremiss' | 'bordlaggning' | null
    }[]
  }[]
  summa: { arenden: number; aterremisser: number; bordlaggningar: number }
}

export type Avvikelsekategori = 'motsagelse' | 'ofullstandigt' | 'paragrafer' | 'tolkning'

export interface Avvikelser {
  fran: number
  till: number
  organ: Organ | null
  kategorier: { id: Avvikelsekategori; namn: string; i_protokollet: boolean; antal: number }[]
  sammantraden: {
    sammantrade: Kortsammantrade & { tolkning: string }
    url: string
    avvikelser: { text: string; kategori: Avvikelsekategori }[]
    i_protokollet: boolean
    rattelser: number
  }[]
  granskade: number
}

export interface Namngiven {
  namn: string
  parti: string | null
  ledamot_id: number | null
}

export type Rostval = 'ja' | 'nej' | 'avstar' | 'franvarande'

export interface Rostantal {
  ja: number | null
  nej: number | null
  avstar: number | null
  franvarande: number | null
}

export interface Votering {
  nummer: number
  ja_forslag: string | null
  nej_forslag: string | null
  /** Siffrorna som protokollets text anger. */
  angivet: Rostantal
  /** Räknat ur voteringslistan. */
  lista: { ja: number; nej: number; avstar: number; franvarande: number }
  resultat: string | null
  /** Vilket förslag som vann enligt protokollets text. Null när det inte går att avgöra. */
  vinnare: 'ja' | 'nej' | null
  roster: {
    /** Null för en tom stol utan namn. */
    namn: string | null
    parti: string | null
    rost: Rostval
    ledamot_id: number | null
    ersatt: Namngiven | null
    rattelser: Rattelser | null
  }[]
  per_parti: { parti: string | null; ja: number; nej: number; avstar: number; franvarande: number }[]
}

export interface Sammantrade extends Sammantradesrad {
  narvaro: Person[]
  behandlingar: Behandlingsrad[]
}

export interface Behandling extends Behandlingsrad {
  sammantrade: Sammantradesrad
  beslutande: Person[]
  jav: Person[]
  /** Ärendet behandlingen hör till (ADR-0003). */
  arende: { id: number; antal_behandlingar: number } | null
  foregaende: number | null
  nasta: number | null
  yrkanden: { text: string; personer: Namngiven[] }[]
  propositionsordning: string | null
  voteringar: Votering[]
  reservationer: { text: string; personer: Namngiven[]; partier: string[] }[]
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
export const hamtaBehandlingsstatistik = (fran?: string, till?: string, organ?: string) => {
  const p = new URLSearchParams()
  if (fran) p.set('fran', fran)
  if (till) p.set('till', till)
  if (organ) p.set('organ', organ)
  return hamta<Behandlingsstatistik>(`/api/statistik/behandlingar?${p}`)
}
function intervallparametrar(fran?: string, till?: string, organ?: string) {
  const p = new URLSearchParams()
  if (fran) p.set('fran', fran)
  if (till) p.set('till', till)
  if (organ) p.set('organ', organ)
  return p
}
export const hamtaBehandlingarAvTyp = (typ: string, fran?: string, till?: string, organ?: string) =>
  hamta<Statistikbehandling[]>(`/api/statistik/behandlingar/${typ}?${intervallparametrar(fran, till, organ)}`)
export const hamtaMotionsstatistik = (fran?: string, till?: string, organ?: string) =>
  hamta<Motionsstatistik>(`/api/statistik/motioner?${intervallparametrar(fran, till, organ)}`)
export const hamtaAterkommande = (fran?: string, till?: string, organ?: string) =>
  hamta<Aterkommande>(`/api/statistik/aterkommande?${intervallparametrar(fran, till, organ)}`)
export const hamtaAvvikelser = (fran?: string, till?: string, organ?: string) =>
  hamta<Avvikelser>(`/api/avvikelser?${intervallparametrar(fran, till, organ)}`)
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
    parti_harlett: PartiHarlett | null
    rattelser: Rattelser | null
    roll: string | null
    kategori: 'beslutande' | 'ej_tjanstgorande' | 'franvarande'
    tjanstgor_for: { namn: string; parti: string | null } | null
    /** Alla tjänstgöringar vid sammanträdet. En ersättare kan tjänstgöra för flera ledamöter. */
    tjanstgoringar: { namn: string; parti: string | null; paragrafer: number[] | null }[]
    paragrafer: number[] | null
    jav: number[]
  }[]
  /** Röster i voteringar, senaste först. */
  roster: {
    sammantrade: { id: number; datum: string | null; organ: Organ }
    paragraf: number
    rubrik: string
    votering: number
    antal_voteringar: number
    namn: string
    parti: string | null
    rost: Rostval
    ersatt: { namn: string; parti: string | null } | null
    ja_forslag: string | null
    nej_forslag: string | null
    vinnare: 'ja' | 'nej' | null
    resultat: string | null
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

// Ärendespårning (#32, ADR-0003)

export type Kopplingsstatus = 'automatisk' | 'forslag' | 'bekraftad' | 'avvisad'

export interface Behandlingsref {
  sammantrade: { id: number; datum: string | null; organ: Organ }
  paragraf: number
  rubrik: string
}

export interface Koppling {
  id: number
  /** Den tidigare behandlingen. */
  fran: Behandlingsref
  till: Behandlingsref
  grund: 'diarienummer' | 'hanvisning'
  /** Diarienumret, eller hänvisningen som den står i beslutsunderlaget. */
  underlag: string
  status: Kopplingsstatus
  redaktor: string | null
  beslutad: string | null
}

export interface Arende {
  id: number
  rubrik: string | null
  diarienummer: string[]
  /** I tidsordning. */
  behandlingar: (Behandlingsref & { diarienummer: string[]; beslut: string | null })[]
  kopplingar: Koppling[]
  /** Det senaste beslutet, om det inte är ett förslag till ett annat organ. */
  slutligt_beslut: { sammantrade_id: number; paragraf: number; organ: Organ; datum: string | null; beslut: string } | null
}

export const hamtaArende = (id: number | string) => hamtaEllerSaknas<Arende>(`/api/arenden/${id}`)

export async function hamtaKopplingar(status: Kopplingsstatus = 'forslag'): Promise<Koppling[]> {
  const svar = await fetch(`/api/kopplingar?status=${status}`)
  if (svar.status === 401) throw new EjInloggad()
  if (svar.status === 403) throw new Error('Kräver rollen redaktör.')
  if (!svar.ok) throw new Error(`API-fel ${svar.status}`)
  return svar.json()
}

async function beslutaKoppling(id: number, beslut: 'bekraftelse' | 'avvisning'): Promise<Koppling> {
  const svar = await fetch(`/api/kopplingar/${id}/${beslut}`, { method: 'POST' })
  if (svar.status === 401) throw new EjInloggad()
  if (svar.status === 403) throw new Error('Kräver rollen redaktör.')
  if (!svar.ok) throw new Error((await svar.json().catch(() => null))?.detail ?? `API-fel ${svar.status}`)
  return svar.json()
}
export const bekraftaKoppling = (id: number) => beslutaKoppling(id, 'bekraftelse')
export const avvisaKoppling = (id: number) => beslutaKoppling(id, 'avvisning')

// Redaktionella rättelser (#33)

/** En publicerad rättelse av en uppgift. Värdet i fältet är det rättade, `ursprungligt` vad tolkningen sa. */
export interface Rattelsemarkering {
  id: number
  ursprungligt: unknown
  nytt: unknown
  motivering: string
  publicerad: string
}
export type Rattelser = Partial<Record<string, Rattelsemarkering>>

export type Rattelsestatus = 'utkast' | 'granskad' | 'publicerad' | 'ersatt'

export interface NyRattelse {
  sammantrade_id: number
  objekt: 'behandling' | 'rost' | 'narvaro'
  paragraf?: number
  votering?: number
  namn?: string
  falt: 'rubrik' | 'beslut' | 'diarienummer' | 'typ' | 'rost' | 'parti'
  nytt: unknown
  motivering: string
}

export interface Rattelse extends Omit<NyRattelse, 'paragraf' | 'votering' | 'namn'> {
  id: number
  sammantrade: { id: number; datum: string | null; organ: Organ }
  paragraf: number | null
  votering: number | null
  namn: string | null
  /** Behandlingens rubrik enligt tolkningen. */
  rubrik: string | null
  ursprungligt: unknown
  status: Rattelsestatus
  redaktor: string
  skapad: string
  granskad_av: string | null
  granskad: string | null
  publicerad_av: string | null
  publicerad: string | null
}

async function skrivRattelse(url: string, metod: string, data?: unknown): Promise<Rattelse | null> {
  const svar = await fetch(url, {
    method: metod,
    headers: data === undefined ? undefined : { 'Content-Type': 'application/json' },
    body: data === undefined ? undefined : JSON.stringify(data),
  })
  if (svar.status === 401) throw new EjInloggad()
  if (!svar.ok) throw new Error((await svar.json().catch(() => null))?.detail ?? `API-fel ${svar.status}`)
  return svar.status === 204 ? null : svar.json()
}

export async function hamtaRattelser(status?: Rattelsestatus): Promise<Rattelse[]> {
  const svar = await fetch(`/api/rattelser${status ? `?status=${status}` : ''}`)
  if (svar.status === 401) throw new EjInloggad()
  if (svar.status === 403) throw new Error('Kräver rollen redaktör eller utgivare.')
  if (!svar.ok) throw new Error(`API-fel ${svar.status}`)
  return svar.json()
}
export const skapaRattelse = (r: NyRattelse) => skrivRattelse('/api/rattelser', 'POST', r) as Promise<Rattelse>
export const granskaRattelse = (id: number) =>
  skrivRattelse(`/api/rattelser/${id}/granskning`, 'POST') as Promise<Rattelse>
export const publiceraRattelse = (id: number) =>
  skrivRattelse(`/api/rattelser/${id}/publicering`, 'POST') as Promise<Rattelse>
export const taBortRattelse = (id: number) => skrivRattelse(`/api/rattelser/${id}`, 'DELETE')

// Partiernas budgetförslag (#48) mot gemensamma planförutsättningar (#58)

export interface Skattesats {
  /** Förändring mot planförutsättningarnas skattesats i öre (0 om förslaget inte ändrar den). */
  ore?: number
  /** Skattesatsen i procent, bara för ett år utan planförutsättningar. */
  procent?: number
  /** Sidan i PDF:en. Saknas för ett Word-dokument, som inte har fasta sidor. */
  sida?: number
}
export interface Budgetresultat {
  /** Andel av skatteintäkter, generella bidrag och utjämning. */
  procent: number
  sida?: number
}
/** En åtgärd eller satsning som förslaget anger för en ram (#57), nära originalets text. */
export interface Budgetatgard {
  text: string
  /** Ramens förändring i mnkr, när förslaget anger ett belopp. */
  mnkr?: number
  /** Sidan i PDF:en. Saknas för ett Word-dokument. */
  sida?: number
}
export interface Budgetram {
  organ: string
  mnkr: number
  sida?: number
  atgarder?: Budgetatgard[]
}
/** Hur stor del av ramens förändring åtgärderna förklarar. */
export interface Atgardstackning {
  antal: number
  /** Summan av åtgärdernas belopp, null om inget belopp anges. */
  mnkr: number | null
  /** Ramen ändras men förslaget anger inga åtgärder. */
  saknas: boolean
}
/** Uppgifterna för budgetåret. */
export interface Budgetuppgifter {
  skattesats: Skattesats
  resultat: Budgetresultat | null
  ramar: Budgetram[]
}
/** Det som skickas vid rättning: ramar kan anges som förändring, skatten som förändring i öre. */
export interface Budgetuppgifterin {
  skattesats: Skattesats
  resultat: Budgetresultat | null
  ramar: (Omit<Budgetram, 'mnkr'> & { mnkr?: number; forandring?: number })[]
}
/** Det som räknas fram ur förslaget och planförutsättningarna. */
export interface Budgetberakning {
  planforutsattningar: boolean
  skattesats: { procent: number | null; ore: number | null; plan: number | null }
  /** Skatteintäkternas förändring i mnkr. */
  skattejustering: number | null
  ramar: { organ: string; mnkr: number; plan: number | null; forandring: number | null; atgarder: Atgardstackning }[]
  /** Summan av förändringarna per nämnd. */
  forandring: number | null
  resultat: { procent: number; mnkr: number | null } | null
  plan_resultat: number | null
  /** Planförutsättningarnas resultat − förändringarna + skatteförändringen. */
  beraknat: number | null
  /** Förslagets resultat − det beräknade. */
  differens: number | null
}
export interface Differens {
  mnkr: number
  procent: number | null
}
export type Budgetstatus = 'utkast' | 'granskad' | 'publicerad' | 'ersatt'
export interface Budgetforslag {
  id: number
  budgetar: number
  nyckel: string
  partier: string[]
  titel: string
  typ: 'budget' | 'tillagg'
  antagen: boolean
  filnamn: string
  anmarkning: string
  status: Budgetstatus
  uppgifter: Budgetuppgifter
  /** Saknas för ett ersatt förslag i formatet före #58. */
  berakning: Budgetberakning | null
  /** Länk till originaldokumentet. Lägg till `#page=N` för en sida. */
  original: string
  publicerad: string | null
  differens?: {
    /** Öre. */
    skattesats: number | null
    resultat: Differens | null
    ramar: (Differens & { organ: string })[]
  } | null
}
export interface Budgetutkast extends Budgetforslag {
  redaktorer: string[]
  granskad_av: string | null
  granskad: string | null
  publicerad_av: string | null
  andrad: string
  inlast: Budgetuppgifter
}
export interface Kalla {
  text: string
  /** Förslaget som källan hänvisar till, och sidan i det. */
  forslag?: number
  sida?: number
}
export interface Planpost {
  post: string
  mnkr: number
  kalla: string
  kallor: Kalla[]
}
export type Plantabell = 'resultatbudget' | 'namnder' | 'investeringar' | 'balansbudget' | 'kassaflode'
export interface Kontroll {
  tabell: Plantabell
  post: string
  summa?: number
  angivet?: number
  differens?: number
  procent?: number
}
export interface Planforutsattningar {
  id: number
  budgetar: number
  status: Budgetstatus
  filnamn: string
  skattesats: { procent: number; kalla: string; kallor: Kalla[] }
  tabeller: Record<Plantabell, Planpost[]>
  kontroller: Kontroll[]
  publicerad: string | null
}
export interface Planutkast extends Planforutsattningar {
  redaktorer: string[]
  granskad_av: string | null
  granskad: string | null
  andrad: string
}
export interface Budgetjamforelse {
  budgetar: number
  organ: string[]
  antagen: number | null
  planforutsattningar: Planforutsattningar | null
  forslag: Budgetforslag[]
}

export const hamtaBudgetar = () =>
  hamta<{ budgetar: number; forslag: number; antagen: boolean }[]>('/api/budget')
export const hamtaBudget = (ar: number) => hamta<Budgetjamforelse>(`/api/budget/${ar}`)
export async function hamtaBudgetutkast(status?: Budgetstatus): Promise<Budgetutkast[]> {
  const svar = await fetch(`/api/budgetforslag${status ? `?status=${status}` : ''}`)
  if (svar.status === 401) throw new EjInloggad()
  if (svar.status === 403) throw new Error('Kräver rollen redaktör eller utgivare.')
  if (!svar.ok) throw new Error(`API-fel ${svar.status}`)
  return svar.json()
}
export const andraBudgetforslag = (
  id: number,
  data: Partial<Pick<Budgetforslag, 'partier' | 'titel' | 'antagen' | 'anmarkning'>> & { uppgifter?: Budgetuppgifterin },
) => skrivRattelse(`/api/budgetforslag/${id}`, 'PATCH', data) as unknown as Promise<Budgetutkast>
export const granskaBudgetforslag = (id: number) =>
  skrivRattelse(`/api/budgetforslag/${id}/granskning`, 'POST') as unknown as Promise<Budgetutkast>
export const publiceraBudgetforslag = (id: number) =>
  skrivRattelse(`/api/budgetforslag/${id}/publicering`, 'POST') as unknown as Promise<Budgetutkast>
export async function hamtaPlanutkast(status?: Budgetstatus): Promise<Planutkast[]> {
  const svar = await fetch(`/api/planforutsattningar${status ? `?status=${status}` : ''}`)
  if (svar.status === 401) throw new EjInloggad()
  if (svar.status === 403) throw new Error('Kräver rollen redaktör eller utgivare.')
  if (!svar.ok) throw new Error(`API-fel ${svar.status}`)
  return svar.json()
}
export const granskaPlanforutsattningar = (id: number) =>
  skrivRattelse(`/api/planforutsattningar/${id}/granskning`, 'POST') as unknown as Promise<Planutkast>
export const publiceraPlanforutsattningar = (id: number) =>
  skrivRattelse(`/api/planforutsattningar/${id}/publicering`, 'POST') as unknown as Promise<Planutkast>
