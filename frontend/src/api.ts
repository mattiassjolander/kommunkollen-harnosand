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

/** En rad i SKR:s prognosunderlag, i tkr per år. */
export interface Prognosrad {
  id: string
  etikett: string
  tkr: Record<string, number>
}
/** SKR:s skatteunderlagsprognos för kommunen, publicerad med ett cirkulär (#61). */
export interface Skatteunderlagsprognos {
  cirkular: string
  version: number
  publicerad: string
  /** Filen på SKR:s sida, källhänvisningen. */
  url: string
  filnamn: string
  /** Skattesatsen prognosen räknar med, i procent. */
  skattesats: number
  ar: number[]
  rader: Prognosrad[]
  /** Antal invånare i kommunen enligt riksprognosen. */
  invanare: Record<string, number>
  hamtad: string
}
export interface Skatteunderlagsprognoser {
  kommun: string
  senaste: Skatteunderlagsprognos | null
  /** Sorterade efter publiceringsdatum. */
  prognoser: Skatteunderlagsprognos[]
}
export const hamtaSkatteunderlagsprognoser = () => hamta<Skatteunderlagsprognoser>('/api/skatteunderlagsprognoser')

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
  /** Publicerade rättelser av fel i själva protokollet (#74). Fler än 0: "Innehåller felaktigheter". */
  felaktigheter: number
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
  /** Satt när en fastställd partitillhörighet (#100) ändrade partiet som protokollet anger. */
  partitillhorighet?: Periodmarkering | null
}

/** Pålägget när en fastställd partitillhörighet gäller vid sammanträdet och ändrar partiet (#100, ADR-0006). */
export interface Periodmarkering {
  id: number
  /** Partiet som protokollet anger, null om det inte anger något. */
  protokollet: string | null
  fran: string
  /** null = tills vidare. */
  till: string | null
  motivering: string
  publicerad: string | null
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
    lista: (Forlopp & {
      motionarer: Motionar[]
      /** Behandlingen som en rättelse av motionärerna hör till (#78). */
      rattelsemal: { sammantrade_id: number; paragraf: number }
      rattelser?: { motionarer?: Rattelsemarkering }
    })[]
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

export type Avvikelsekategori = 'motsagelse' | 'felskrivet' | 'ofullstandigt' | 'paragrafer' | 'tolkning'

/** En publicerad rättelse i listan över felaktigheter (#74). */
export interface Avvikelserattelse {
  id: number
  objekt: NyRattelse['objekt']
  paragraf: number | null
  votering: number | null
  namn: string | null
  rubrik: string | null
  falt: NyRattelse['falt']
  ursprungligt: unknown
  nytt: unknown
  motivering: string
  felet_i: FeletI | null
  publicerad: string
}

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
    /** Publicerade rättelser av fel i protokollet. */
    felaktigheter: number
    rattelser: Avvikelserattelse[]
  }[]
  felet_i: { id: FeletI | null; antal: number }[]
  granskade: number
}

export interface Namngiven {
  namn: string
  parti: string | null
  ledamot_id: number | null
  partitillhorighet?: Periodmarkering | null
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
    partitillhorighet?: Periodmarkering | null
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
/** En motionär: en person i registret med parti, eller ett parti utan namn (en partigrupp). */
export interface Motionar {
  person_id: number | null
  namn: string | null
  parti: string | null
  partitillhorighet?: Periodmarkering | null
}

/** Förslag på parti för en motionär vid sammanträdet där motionen väcktes, med källa (#78). */
export interface Partiforslag {
  parti: string | null
  kalla: {
    grund: 'partitillhorighet' | 'narvaro' | 'samma_protokoll' | 'annat_protokoll'
    sammantrade: { id: number; datum: string | null; organ: Organ } | null
  } | null
}
export const hamtaMotionarParti = (personId: number, sammantradeId: number) =>
  hamta<Partiforslag>(`/api/motionarer/parti?person_id=${personId}&sammantrade_id=${sammantradeId}`)

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
  /** Publicerade fastställda partitillhörigheter (#100), äldst först. */
  partitillhorighet: Partitillhorighet[]
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
    partitillhorighet: Periodmarkering | null
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
    partitillhorighet?: Periodmarkering | null
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
  grund: 'diarienummer' | 'hanvisning' | 'motionstitel'
  /** Diarienumret, hänvisningen som den står i beslutsunderlaget, eller motionens normaliserade titel. */
  underlag: string
  status: Kopplingsstatus
  /** Redaktören som fattade det senaste beslutet, och när. */
  redaktor: string | null
  beslutad: string | null
  /** Alla beslut om kopplingen, äldst först (#77). Skrivs aldrig över. */
  historik: Kopplingsbeslut[]
}

export interface Kopplingsbeslut {
  status: Exclude<Kopplingsstatus, 'automatisk'>
  redaktor: string
  tid: string
  /** Krävs när ett tidigare beslut ändras. */
  motivering: string | null
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

export async function hamtaKopplingar(status: Kopplingsstatus = 'forslag', mina = false): Promise<Koppling[]> {
  const svar = await fetch(`/api/kopplingar?status=${status}${mina ? '&mina=true' : ''}`)
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

/** Ändrar ett tidigare beslut om en koppling, med motivering (#77). */
export async function andraKopplingsbeslut(
  id: number,
  status: Exclude<Kopplingsstatus, 'automatisk'>,
  motivering: string,
): Promise<Koppling> {
  const svar = await fetch(`/api/kopplingar/${id}/beslut`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ status, motivering }),
  })
  if (svar.status === 401) throw new EjInloggad()
  if (svar.status === 403) throw new Error('Kräver rollen redaktör.')
  if (!svar.ok) throw new Error((await svar.json().catch(() => null))?.detail ?? `API-fel ${svar.status}`)
  return svar.json()
}

// Redaktionella rättelser (#33)

/** En publicerad rättelse av en uppgift. Värdet i fältet är det rättade, `ursprungligt` vad tolkningen sa. */
export interface Rattelsemarkering {
  id: number
  ursprungligt: unknown
  nytt: unknown
  motivering: string
  felet_i?: FeletI | null
  publicerad: string
  /** Tidigare publicerade versioner av rättelsen, senaste först (#74). */
  tidigare?: { nytt: unknown; motivering: string; felet_i: FeletI | null; publicerad: string }[]
}

/** Var felet som en rättelse rättar finns (#74). null: inte angivet (rättelser från före #74). */
export type FeletI = 'protokollet' | 'inlasningen'
export const FELET_I: Record<FeletI | 'ej_angivet', string> = {
  protokollet: 'I protokollet',
  inlasningen: 'I inläsningen',
  ej_angivet: 'Inte angivet',
}
export type Rattelser = Partial<Record<string, Rattelsemarkering>>

export type Rattelsestatus = 'utkast' | 'granskad' | 'publicerad' | 'ersatt' | 'aterkallad'

export interface NyRattelse {
  sammantrade_id: number
  objekt: 'behandling' | 'rost' | 'narvaro'
  paragraf?: number
  votering?: number
  namn?: string
  falt: 'rubrik' | 'beslut' | 'diarienummer' | 'typ' | 'rost' | 'parti' | 'motionarer'
  nytt: unknown
  motivering: string
  felet_i: FeletI
}

export interface Rattelse extends Omit<NyRattelse, 'paragraf' | 'votering' | 'namn' | 'felet_i'> {
  id: number
  sammantrade: { id: number; datum: string | null; organ: Organ }
  paragraf: number | null
  votering: number | null
  namn: string | null
  /** Behandlingens rubrik enligt tolkningen. */
  rubrik: string | null
  ursprungligt: unknown
  felet_i: FeletI | null
  status: Rattelsestatus
  redaktor: string
  skapad: string
  granskad_av: string | null
  granskad: string | null
  publicerad_av: string | null
  publicerad: string | null
  /** Versionen den här ersätter när den publiceras (#74). */
  ersatter_id: number | null
  aterkallad_av: string | null
  aterkallad: string | null
  aterkallelse: string | null
  /** Tidigare versioner som den här ersätter, senaste först. */
  tidigare: Rattelse[]
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
/** En ny version av en granskad eller publicerad rättelse, som utkast (#74). */
export const nyVersionAvRattelse = (id: number, data: { nytt?: unknown; motivering: string; felet_i: FeletI | null }) =>
  skrivRattelse(`/api/rattelser/${id}/versioner`, 'POST', data) as Promise<Rattelse>
/** En utgivare återkallar en publicerad rättelse direkt. Tolkningen gäller igen. */
export const aterkallaRattelse = (id: number, motivering: string) =>
  skrivRattelse(`/api/rattelser/${id}/aterkallelse`, 'POST', { motivering }) as Promise<Rattelse>

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
  /** Redaktören har läst av åtgärderna för ramen. En tom lista betyder att förslaget inte anger några. */
  avlast: boolean
  /** Ramen ändras men förslaget anger enligt avläsningen inga åtgärder. */
  saknas: boolean
}
/** Hänvisningen till behandlingen där förslaget ställdes. */
export interface Behandlingshanvisning {
  organ: string
  /** ÅÅÅÅ-MM-DD. */
  datum: string
  paragraf: number
}
/** Ett svar i summeringen: vad förslaget säger, med sidorna, eller att förslaget inte tar upp frågan. */
export type Summeringssvar = { text: string; sidor?: number[] } | { anges_inte: true }
/** Uppgifterna för budgetåret. */
export interface Budgetuppgifter {
  skattesats: Skattesats
  resultat: Budgetresultat | null
  ramar: Budgetram[]
  behandling?: Behandlingshanvisning
  /** Ett svar per fråga i mallen (#48). */
  summering?: Record<string, Summeringssvar>
}
/** Behandlingen där förslaget ställdes, med partiets yrkande och voteringarna. Yrkandet och sidan i
 * voteringen är automatiskt kopplade. */
export interface Behandlingskoppling extends Behandlingshanvisning {
  /** False när behandlingen inte finns i plattformen. */
  hittad: boolean
  sammantrade_id: number | null
  rubrik: string | null
  yrkanden: { text: string; personer: { namn: string; parti: string | null; ledamot_id: number | null }[] }[]
  voteringar: {
    nummer: number
    ja_forslag: string | null
    nej_forslag: string | null
    vinnare: 'ja' | 'nej' | null
    lista: { ja: number; nej: number; avstar: number; franvarande: number }
    /** Sidan förslaget stod på, när förslagsställarens namn står i voteringen. */
    sida: 'ja' | 'nej' | null
  }[]
}
export interface Summeringsfraga {
  id: string
  fraga: string
}
export type Summeringsrad = Summeringsfraga & { text?: string; sidor?: number[]; anges_inte?: true }
/** Det som skickas vid rättning: ramar kan anges som förändring, skatten som förändring i öre. */
export interface Budgetuppgifterin {
  skattesats: Skattesats
  resultat: Budgetresultat | null
  ramar: (Omit<Budgetram, 'mnkr'> & { mnkr?: number; forandring?: number })[]
  behandling?: Partial<Behandlingshanvisning>
  summering?: Record<string, Summeringssvar>
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
  behandling: Behandlingskoppling | null
  /** Summeringen i mallens ordning, märkt Analys. Null om förslaget inte har någon. */
  summering: Summeringsrad[] | null
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
  /** Summeringens frågor, för att skriva en summering. */
  mall: Summeringsfraga[]
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
  /** Summeringens frågor, samma för alla förslag. */
  mall: Summeringsfraga[]
  forslag: Budgetforslag[]
  /** Planförutsättningarnas skatteintäkter och generella bidrag och utjämning mot SKR:s prognoser (#62). */
  skr: SkrJamforelse
}

export interface SkrJamforelse {
  planforutsattningar_mnkr: number | null
  /** En rad per skatteunderlagsprognos med en siffra för budgetåret, sorterade efter publiceringsdatum. */
  prognoser: {
    cirkular: string
    publicerad: string
    url: string
    filnamn: string
    mnkr: number
    /** SKR − planförutsättningar. */
    differens: { mnkr: number; procent: number | null } | null
  }[]
  /** Varför jämförelsen saknas, annars null. */
  saknas: string | null
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

// Sammanträdesplaner (#68): organens planer så som webbsidan visar dem, och skillnaderna mot besluten i
// protokollen. Bara för redaktionen.
export type Planstatus = 'planerat' | 'installt' | 'borttaget'
/** Varifrån planen kommer: tabellen på webbsidan, eller organets beslut i protokollet innan tabellen finns (#99). */
export type Plankalla = 'webbsidan' | 'beslut'

export interface Planversion {
  version: number
  datum: string | null
  starttid: string | null
  status: Planstatus
  anmarkning: string | null
  kalltext: string
  hamtad: string
  kalla: Plankalla
}

export interface PlaneratSammantrade {
  id: number
  nyckel: string
  datum: string | null
  manad: string
  starttid: string | null
  status: Planstatus
  anmarkning: string | null
  version: number
  protokoll: boolean
  kalla: Plankalla
  beslut: { sammantrade_id: number; paragraf: number; datum: string } | null
  versioner: Planversion[]
}

export interface Planskillnad {
  datum: string
  typ: 'bara_sidan' | 'bara_beslutet' | 'tid'
  sidan: string | null
  beslutet: string | null
}

export interface Sammantradesplan {
  organ: { id: string; namn: string }
  ar: number
  url: string | null
  sammantraden: PlaneratSammantrade[]
  /** Webbsidan har ingen plan för året än: alla sammanträden kommer från beslut i protokollen. */
  bara_beslut: boolean
  beslut: { sammantrade_id: number; paragraf: number; rubrik: string; datum: string }[]
  skillnader: Planskillnad[] | null
}

export async function hamtaSammantradesplaner(): Promise<Sammantradesplan[]> {
  const svar = await fetch('/api/sammantradesplaner')
  if (svar.status === 401) throw new EjInloggad()
  if (svar.status === 403) throw new Error('Kräver rollen redaktör.')
  if (!svar.ok) throw new Error(`API-fel ${svar.status}`)
  return svar.json()
}

// Kalendern över sammanträden (#68). Flödena ligger på /kalender/<flode>.ics och är öppna utan inloggning.
export interface Kalenderhandelse {
  id: number
  uid: string
  organ: { id: string; namn: string; flode: string }
  datum: string
  starttid: string | null
  sluttid: string | null
  sluttid_ungefarlig: boolean
  plats: string | null
  plats_antagen: boolean
  plats_kalla: 'protokoll' | 'kallelse' | 'antagen' | null
  status: 'planerat' | 'installt' | 'borttaget' | 'hallet'
  kallelse: { titel: string; url: string; typ: 'kungorelse' | 'kallelse' } | null
  handlingar: { titel: string; url: string; storlek: number | null }[]
  webbsandning: { url: string; inspelning: boolean } | null
  protokoll: boolean
  sekvens: number
  andrad: string | null
  plan_url: string | null
  /** Planerat enligt ett beslut i protokollet, när webbsidan saknar plan för året (#99). */
  beslut: { sammantrade_id: number; paragraf: number; datum: string; organ: { id: string; namn: string } } | null
}

export interface Kalender {
  idag: string
  floden: { organ: string; namn: string; flode: string }[]
  handelser: Kalenderhandelse[]
}

export async function hamtaKalender(): Promise<Kalender> {
  const svar = await fetch('/api/kalender')
  if (svar.status === 401) throw new EjInloggad()
  if (!svar.ok) throw new Error(`API-fel ${svar.status}`)
  return svar.json()
}

// Kommande: ärenden som inte är avslutade (automatiskt tolkade uppgifter)

export type Kommandestatus = 'motion' | 'medborgarforslag' | 'aterremiss' | 'bordlaggning' | 'forslag' | 'uppdrag'

export interface Kommandearende {
  arende_id: number
  rubrik: string
  status: Kommandestatus
  /** Organet som ska fatta nästa beslut, när det framgår. */
  vantar_pa: Organ | null
  /** Sedan när ärendet väntar: väckt (motioner) eller senaste behandlingen. */
  sedan: string
  /** För motioner: om datumet är när motionen väcktes, annars är det första behandlingen. */
  vackt: boolean
  dagar: number
  /** Obesvarad motion eller medborgarförslag i mer än ett år. */
  over_ett_ar: boolean
  /** Tidpunkt för återrapportering som beslutet anger, som det står. */
  frist: string | null
  /** Som protokollet anger dem. Namnet saknas när bara partiet anges. */
  motionarer: { namn: string | null; parti: string | null }[]
  diarienummer: string[]
  antal_behandlingar: number
  senaste: Behandlingsref & { beslut: string | null }
}

export interface Kommande {
  idag: string
  manader: number
  statusar: { id: Kommandestatus; namn: string; antal: number }[]
  arenden: Kommandearende[]
}

export interface Underlagsbehandling extends Behandlingsref {
  diarienummer: string[]
  beslut: string | null
  protokoll: Protokollkalla | null
  /** Hänvisningar i beslutsunderlaget, med behandlingen de pekar på när den finns i protokollen. */
  hanvisningar: { text: string; behandling: { sammantrade_id: number; paragraf: number } | null }[]
}

export interface Arendeunderlag extends Omit<Arende, 'behandlingar'> {
  behandlingar: Underlagsbehandling[]
}

export const hamtaKommande = (manader?: number) =>
  hamta<Kommande>(`/api/kommande${manader ? `?manader=${manader}` : ''}`)
export const hamtaArendeunderlag = (id: number | string) => hamtaEllerSaknas<Arendeunderlag>(`/api/kommande/${id}`)

// Fastställd partitillhörighet per period (#100, ADR-0006)

export type Periodstatus = 'utkast' | 'granskad' | 'publicerad' | 'ersatt' | 'aterkallad'
export interface Partitillhorighet {
  id: number
  /** Personen, under huvudnamnet. */
  ledamot: { id: number; namn: string }
  /** Partiförkortning, '-' för partilös. */
  parti: string
  fran: string
  /** null = tills vidare. */
  till: string | null
  motivering: string
  status: Periodstatus
  ersatter_id: number | null
  /** Satt när perioden bekräftades tillsammans med andra förslag (#100, del 2). */
  batch: number | null
  redaktor: string
  skapad: string
  granskad_av: string | null
  granskad: string | null
  publicerad_av: string | null
  publicerad: string | null
  aterkallad_av: string | null
  aterkallad: string | null
  aterkallelse: string | null
}
export interface NyPartitillhorighet {
  ledamot_id: number
  parti: string
  fran: string
  till: string | null
  motivering: string
}

const skrivPeriod = (url: string, metod: string, data?: unknown) =>
  skrivRattelse(url, metod, data) as unknown as Promise<Partitillhorighet>

export async function hamtaPartitillhorigheter(): Promise<Partitillhorighet[]> {
  const svar = await fetch('/api/partitillhorighet')
  if (svar.status === 401) throw new EjInloggad()
  if (svar.status === 403) throw new Error('Kräver rollen redaktör eller utgivare.')
  if (!svar.ok) throw new Error(`API-fel ${svar.status}`)
  return svar.json()
}
export const skapaPartitillhorighet = (p: NyPartitillhorighet) => skrivPeriod('/api/partitillhorighet', 'POST', p)
export const taBortPartitillhorighet = (id: number) => skrivRattelse(`/api/partitillhorighet/${id}`, 'DELETE')
export const granskaPartitillhorighet = (id: number) => skrivPeriod(`/api/partitillhorighet/${id}/granskning`, 'POST')
export const publiceraPartitillhorighet = (id: number) =>
  skrivPeriod(`/api/partitillhorighet/${id}/publicering`, 'POST')
/** En ny version av en granskad eller publicerad period, som utkast. Den ersätter den gamla när den publiceras. */
export const nyVersionAvPartitillhorighet = (id: number, data: Partial<Omit<NyPartitillhorighet, 'ledamot_id'>>) =>
  skrivPeriod(`/api/partitillhorighet/${id}/versioner`, 'POST', data)
/** En utgivare återkallar en publicerad period direkt. Protokollen gäller igen. */
export const aterkallaPartitillhorighet = (id: number, motivering: string) =>
  skrivPeriod(`/api/partitillhorighet/${id}/aterkallelse`, 'POST', { motivering })

/** En föreslagen period ur närvarolistorna, med belägg (#100, del 2). */
export interface Periodforslag {
  parti: string
  fran: string
  till: string | null
  /** Antal sammanträden per angivet parti inom perioden. */
  antal_per_parti: Record<string, number>
  /** Sammanträden inom perioden där närvarolistan inte anger parti. */
  utan_parti: number
  forsta: string | null
  sista: string | null
  exempel: { id: number; datum: string; organ: Organ } | null
  /** Sammanträden inom perioden där protokollet anger ett annat parti. */
  krockar: { id: number; datum: string; organ: Organ; parti: string }[]
}
export interface Personforslag {
  ledamot: { id: number; namn: string }
  perioder: Periodforslag[]
}
export async function hamtaPeriodforslag(): Promise<Personforslag[]> {
  const svar = await fetch('/api/partitillhorighet/forslag')
  if (svar.status === 401) throw new EjInloggad()
  if (!svar.ok) throw new Error(`API-fel ${svar.status}`)
  return svar.json()
}
export const skapaPeriodbatch = (data: {
  motivering: string
  perioder: (NyPartitillhorighet | Omit<NyPartitillhorighet, 'motivering'>)[]
}) => skrivRattelse('/api/partitillhorighet/batcher', 'POST', data) as unknown as Promise<Partitillhorighet[]>
export const granskaPeriodbatch = (batch: number) =>
  skrivRattelse(`/api/partitillhorighet/batcher/${batch}/granskning`, 'POST') as unknown as Promise<Partitillhorighet[]>
export const publiceraPeriodbatch = (batch: number) =>
  skrivRattelse(`/api/partitillhorighet/batcher/${batch}/publicering`, 'POST') as unknown as Promise<Partitillhorighet[]>

/** En krock: närvarolistan anger ett annat parti än personens fastställda partitillhörighet (#100, del 3). */
export interface Krock {
  sammantrade: { id: number; datum: string; organ: Organ }
  /** Namnet som i närvarolistan. */
  namn: string
  protokollet: string
  period: { id: number; parti: string; fran: string; till: string | null; status: Periodstatus }
}
export interface Personkrockar {
  ledamot: { id: number; namn: string }
  krockar: Krock[]
}
export interface Periodperson {
  ledamot: { id: number; namn: string }
  antal_sammantraden: number
  senast: string | null
  publicerade: Partitillhorighet[]
  /** Perioder som är utkast eller granskade. */
  vantande: number
  krockar: number
}
export const hamtaKrockar = () => hamta<Personkrockar[]>('/api/partitillhorighet/krockar')
export const hamtaPeriodpersoner = () => hamta<Periodperson[]>('/api/partitillhorighet/personer')
/** Bekräftar krockar som rättelser av partiet i närvarolistan, som utkast. */
export const bekraftaKrockar = (data: {
  felet_i: FeletI | null
  motivering: string
  krockar: { sammantrade_id: number; namn: string }[]
}) => skrivRattelse('/api/partitillhorighet/krockar/bekraftelser', 'POST', data) as unknown as Promise<Rattelse[]>
