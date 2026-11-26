// Navigeringens katalog (#146, #160, design.md *Navigering*): huvudvyerna och deras undervyer.
// Vänsternavigeringen, brödsmulan och dokumentets titel läser härifrån, så att alla huvudvyer med
// undervyer fungerar likadant. En vy som bara vissa roller får se anger rollerna.

export type Roll = 'redaktor' | 'utgivare'

export interface Undervy {
  till: string
  namn: string
  /** Rubrik i navigeringen som undervyn står under (Redaktion: Granska, Registrera). */
  grupp?: string
  /** Visas bara för dessa roller. Saknas: för alla. */
  roller?: Roll[]
  /** Nyckel för antal som väntar (Redaktion). */
  vantar?: 'rattelser' | 'kopplingar'
}

export interface Huvudvy {
  till: string
  namn: string
  undervyer?: Undervy[]
  roller?: Roll[]
  /** Diskret rad längre ner i navigeringen (Om Kommunkollen). */
  diskret?: boolean
}

const REDAKTION: Roll[] = ['redaktor', 'utgivare']

export const HUVUDVYER: Huvudvy[] = [
  { till: '/', namn: 'Översikt' },
  {
    till: '/ekonomi',
    namn: 'Ekonomi',
    undervyer: [
      { till: '/ekonomi', namn: 'Nyckeltal' },
      { till: '/ekonomi/skatteunderlag', namn: 'Skatteunderlagsprognos' },
      { till: '/ekonomi/budget-och-utfall', namn: 'Budget och utfall' },
      { till: '/ekonomi/floden', namn: 'Ekonomiska flöden' },
    ],
  },
  {
    till: '/politik',
    namn: 'Politik och beslut',
    undervyer: [
      { till: '/politik', namn: 'Sammanträden', grupp: 'Sammanträden' },
      { till: '/politik/kommande', namn: 'Kommande ärenden', grupp: 'Sammanträden' },
      { till: '/politik/kalender', namn: 'Kalender', grupp: 'Sammanträden' },
      { till: '/politik/ledamoter', namn: 'Ledamöter', grupp: 'Förtroendevalda' },
      { till: '/politik/sammansattning', namn: 'Sammansättning', grupp: 'Förtroendevalda' },
      { till: '/politik/budget', namn: 'Budgetförslag', grupp: 'Dokument' },
      { till: '/politik/styrande-dokument', namn: 'Styrande dokument', grupp: 'Dokument' },
      { till: '/politik/statistik', namn: 'Statistik', grupp: 'Uppföljning' },
      { till: '/politik/avvikelser', namn: 'Avvikelser', grupp: 'Uppföljning' },
    ],
  },
  {
    // Gruppen har ingen egen sida. Undervyerna behåller sina adresser, och plats() hittar gruppen genom dem.
    till: '/jamforelse',
    namn: 'Kommunen i jämförelse',
    undervyer: [
      { till: '/rankningar', namn: 'Rankningar' },
      { till: '/undersokningar', namn: 'Undersökningar' },
    ],
  },
  {
    till: '/om',
    namn: 'Om Kommunkollen',
    diskret: true,
    undervyer: [{ till: '/datakallor', namn: 'Datakällor' }],
  },
  {
    till: '/redaktion',
    namn: 'Redaktion',
    roller: REDAKTION,
    undervyer: [
      { till: '/redaktion/rattelser', namn: 'Rättelser', grupp: 'Granska', roller: REDAKTION, vantar: 'rattelser' },
      { till: '/redaktion/kopplingar', namn: 'Kopplingar', grupp: 'Granska', roller: ['redaktor'], vantar: 'kopplingar' },
      { till: '/redaktion/partitillhorighet', namn: 'Partitillhörighet', grupp: 'Granska', roller: REDAKTION },
      { till: '/redaktion/motstridigheter', namn: 'Motstridigheter', grupp: 'Granska', roller: REDAKTION },
      { till: '/redaktion/processer', namn: 'Processer', grupp: 'Granska', roller: REDAKTION },
      { till: '/redaktion/att-anmala', namn: 'Att anmäla', grupp: 'Granska', roller: REDAKTION },
      { till: '/redaktion/sammantradesplaner', namn: 'Sammanträdesplaner', grupp: 'Registrera', roller: ['redaktor'] },
      { till: '/redaktion/budgetutkast', namn: 'Budgetutkast', grupp: 'Registrera', roller: REDAKTION },
    ],
  },
]

/** Vyer som har bytt adress (#146, #160). De gamla adresserna styrs om hit. */
export const FLYTTADE: Record<string, string> = {
  '/politik/rattelser': '/redaktion/rattelser',
  '/politik/kopplingar': '/redaktion/kopplingar',
  '/politik/partitillhorighet': '/redaktion/partitillhorighet',
  '/politik/sammantradesplaner': '/redaktion/sammantradesplaner',
  '/politik/budgetutkast': '/redaktion/budgetutkast',
  '/politik/protokollavvikelser': '/redaktion/att-anmala',
  '/floden': '/ekonomi/floden',
  '/kommande': '/politik/kommande',
  '/kalender': '/politik/kalender',
}

export function synlig(v: { roller?: Roll[] }, roller: readonly string[]): boolean {
  return !v.roller || v.roller.some((r) => roller.includes(r))
}

/** Huvudvyerna med de undervyer rollerna får se. En huvudvy vars undervyer alla är dolda visas inte. */
export function synligaVyer(roller: readonly string[]): Huvudvy[] {
  return HUVUDVYER.filter((h) => synlig(h, roller))
    .map((h) => (h.undervyer ? { ...h, undervyer: h.undervyer.filter((u) => synlig(u, roller)) } : h))
    .filter((h) => !h.undervyer || h.undervyer.length > 0)
}

function under(sokvag: string, till: string): boolean {
  return till === '/' ? sokvag === '/' : sokvag === till || sokvag.startsWith(`${till}/`)
}

export interface Plats {
  huvudvy: Huvudvy
  /** Undervyn sökvägen hör till, också för en detaljsida som /politik/sammantraden/12. */
  undervy: Undervy | null
  /** Sökvägen är undervyn själv, inte en detaljsida under den. */
  exakt: boolean
}

/** Längden på den längsta adress i listan som sökvägen ligger under, eller -1. */
function traff(sokvag: string, adresser: string[]): number {
  return Math.max(-1, ...adresser.filter((t) => under(sokvag, t)).map((t) => t.length))
}

/**
 * Var i navigeringen en sökväg hör hemma. Den längsta matchande adressen vinner. En huvudvy hittas genom sin egen
 * adress eller någon av undervyernas, eftersom Kommunen i jämförelse har undervyer på /rankningar och /undersokningar.
 */
export function plats(sokvag: string): Plats | null {
  const [basta] = HUVUDVYER.map((h) => ({ h, n: traff(sokvag, [h.till, ...(h.undervyer ?? []).map((u) => u.till)]) }))
    .filter((x) => x.n >= 0)
    .sort((a, b) => b.n - a.n)
  if (!basta) return null
  const huvudvy = basta.h
  const undervy =
    (huvudvy.undervyer ?? []).filter((u) => under(sokvag, u.till)).sort((a, b) => b.till.length - a.till.length)[0] ??
    null
  return { huvudvy, undervy, exakt: undervy?.till === sokvag }
}

/** Dokumentets titel: "Statistik · Politik och beslut · Kommunkollen Härnösand". */
export function dokumenttitel(sokvag: string, sidtitel?: string): string {
  const p = plats(sokvag)
  const delar = [sidtitel, p?.undervy && !p.exakt ? p.undervy.namn : null, p?.huvudvy.undervyer ? p.huvudvy.namn : null]
    .filter((d, i, alla): d is string => !!d && alla.indexOf(d) === i)
  return [...delar, 'Kommunkollen Härnösand'].join(' · ')
}
