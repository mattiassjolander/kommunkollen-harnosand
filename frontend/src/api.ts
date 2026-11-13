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

export interface Punkt {
  period: string
  varde: number | null
  kallans_publicering: string | null
  hamtad: string
  version: number
}

export interface Serie {
  matt: Matt
  omrade: string
  punkter: Punkt[]
}

export async function hamtaSerie(mattId: string): Promise<Serie | null> {
  const svar = await fetch(`/api/matt/${encodeURIComponent(mattId)}/serie`)
  if (svar.status === 404) return null
  if (!svar.ok) throw new Error(`API-fel ${svar.status}`)
  return svar.json()
}
