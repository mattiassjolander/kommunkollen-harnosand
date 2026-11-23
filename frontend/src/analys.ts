// Analysverktyg för nyckeltal: mandatperioder, förändring mellan två år och CSV-export.
// Allt här är rena funktioner, så att samma regler gäller i diagram, tabell och export.

import type { Nyckeltal } from './api'
import { siffra, tal } from './format'

// Mandatperioder

/**
 * Valår till kommunfullmäktige. Fullmäktige som väljs ett valår tillträder 15 oktober och styr
 * budgetåren efter valet: mandatperioden 2022–2026 omfattar budgetåren 2023–2026.
 */
const VALAR = [1994, 1998, 2002, 2006, 2010, 2014, 2018, 2022, 2026, 2030]

export interface Mandatperiod {
  /** Första och sista budgetåret i perioden. */
  forsta: number
  sista: number
  /** T.ex. "2022–2026" (valår till valår, som kravspecen skriver mandatperioder). */
  titel: string
}

export function mandatperioder(fran: number, till: number): Mandatperiod[] {
  return VALAR.map((valar) => ({ forsta: valar + 1, sista: valar + 4, titel: `${valar}–${valar + 4}` })).filter(
    (m) => m.sista >= fran && m.forsta <= till,
  )
}

// Förändring mellan två år

/**
 * Tröskel för "större förändring". Dokumenterad i docs/tackning-ekonomi.md.
 * Nyckeltal i procent jämförs i procentenheter, övriga relativt det tidigare värdet.
 */
export const STOR_FORANDRING = { andel: 0.1, procentenheter: 5 }

export interface Forandring {
  fore: number
  efter: number
  /** I nyckeltalets enhet (för %-nyckeltal: procentenheter). */
  skillnad: number
  /** Relativ förändring, t.ex. 0.08. null för %-nyckeltal och när det tidigare värdet är noll. */
  andel: number | null
  stor: boolean
}

export function forandring(fore: number | null, efter: number | null, enhet: string): Forandring | null {
  if (fore === null || efter === null) return null
  const skillnad = efter - fore
  if (enhet.includes('%')) {
    return { fore, efter, skillnad, andel: null, stor: Math.abs(skillnad) >= STOR_FORANDRING.procentenheter }
  }
  // Relativt beloppet, även när det är negativt (t.ex. ett underskott som minskar).
  const andel = fore === 0 ? null : skillnad / Math.abs(fore)
  return { fore, efter, skillnad, andel, stor: andel !== null && Math.abs(andel) >= STOR_FORANDRING.andel }
}

// Jämförelse med riket (#82)

/** Skillnaden mot riket med tecken: "+1,2 procentenheter" eller "−3 400 kr/inv". Ingen värdering. */
export function skillnad(v: number, enhet: string): string {
  const tecken = v > 0 ? '+' : v < 0 ? '−' : '±'
  return enhet.includes('%') ? `${tecken}${siffra(Math.abs(v), enhet)} procentenheter` : `${tecken}${tal(Math.abs(v), enhet)}`
}

/** Värdet per period i en serie. */
export function perPeriod(serie: { punkter: { period: string; varde: number | null }[] } | null): Map<string, number | null> {
  return new Map((serie?.punkter ?? []).map((p) => [p.period, p.varde]))
}

export const OMRADEN: Record<string, string> = { '2280': 'Härnösand', '0000': 'Riket' }

// CSV-export

const KOLUMNER = [
  'Nyckeltal',
  'Mått-id',
  'Period',
  'Värde',
  'Enhet',
  'Prisnivå',
  'Källa',
  'Källans webbplats',
  'Publicerad av källan',
  'Hämtad',
  'Version',
  'Område',
] as const

function cell(v: string | number | null | undefined): string {
  if (v === null || v === undefined) return ''
  // Svenskt Excel: semikolon mellan fält och decimalkomma. Ett saknat värde är en tom cell, aldrig 0.
  const s = typeof v === 'number' ? String(v).replace('.', ',') : v
  return /[";\n\r]/.test(s) ? `"${s.replace(/"/g, '""')}"` : s
}

function exportdatum(iso: string | null): string {
  if (!iso) return ''
  if (/^\d{4}-\d{2}-\d{2}$/.test(iso)) return iso
  return new Intl.DateTimeFormat('sv-SE', { timeZone: 'Europe/Stockholm' }).format(new Date(iso))
}

/** CSV med ett värde per rad, i källans enhet, för åren `fran`–`till`. Med `medRiket` kommer även
 * genomsnittet för riket med, för de nyckeltal som har det. */
export function csv(nyckeltal: Nyckeltal[], fran: number, till: number, medRiket = false): string {
  const rader: string[] = [KOLUMNER.join(';')]
  const serier = nyckeltal.flatMap((n) => [
    { n, s: n.serie },
    ...(medRiket && n.riket ? [{ n, s: n.riket }] : []),
  ])
  for (const { n, s } of serier) {
    if (!s) continue
    for (const p of s.punkter) {
      const ar = Number(p.period)
      if (ar < fran || ar > till) continue
      rader.push(
        [
          s.matt.titel,
          s.matt.id,
          p.period,
          p.varde,
          s.matt.enhet,
          n.prisniva,
          s.matt.datakalla.titel,
          s.matt.datakalla.url,
          exportdatum(p.kallans_publicering ?? s.matt.kallans_publicering),
          exportdatum(p.hamtad),
          p.version,
          OMRADEN[s.omrade] ?? s.omrade,
        ]
          .map(cell)
          .join(';'),
      )
    }
  }
  return rader.join('\r\n') + '\r\n'
}

/** Startar en nedladdning i webbläsaren. BOM så att Excel läser å, ä och ö rätt. */
export function laddaNer(filnamn: string, innehall: string) {
  const url = URL.createObjectURL(new Blob(['﻿', innehall], { type: 'text/csv;charset=utf-8' }))
  const a = Object.assign(document.createElement('a'), { href: url, download: filnamn })
  document.body.append(a)
  a.click()
  a.remove()
  URL.revokeObjectURL(url)
}
