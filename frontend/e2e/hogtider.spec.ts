import { expect, test } from '@playwright/test'
import { midsommarafton, paskdagen, temaFor, valdagen } from '../src/hogtider'

// Enhetstester av datumlogiken för högtidsteman (issue #70). De behöver ingen webbläsare.

const namn = (datum: string) => temaFor(datum)?.namn ?? null
const text = (datum: string) => temaFor(datum)?.text ?? null

test.describe('temaFor', () => {
  test('påsk: skärtorsdag till annandag påsk, 2026 och 2027', () => {
    expect(paskdagen(2026)).toEqual({ ar: 2026, manad: 4, dag: 5 })
    expect(paskdagen(2027)).toEqual({ ar: 2027, manad: 3, dag: 28 })
    expect(namn('2026-04-01')).toBeNull()
    for (const d of ['2026-04-02', '2026-04-03', '2026-04-04', '2026-04-05', '2026-04-06']) {
      expect(namn(d), d).toBe('pask')
    }
    expect(namn('2026-04-07')).toBeNull()
    expect(namn('2027-03-24')).toBeNull()
    for (const d of ['2027-03-25', '2027-03-26', '2027-03-27', '2027-03-28', '2027-03-29']) {
      expect(namn(d), d).toBe('pask')
    }
    expect(namn('2027-03-30')).toBeNull()
    expect(text('2026-04-05')).toBe('Glad påsk')
  })

  test('midsommar: afton och dag, 2026 och 2027', () => {
    expect(midsommarafton(2026)).toEqual({ ar: 2026, manad: 6, dag: 19 })
    expect(midsommarafton(2027)).toEqual({ ar: 2027, manad: 6, dag: 25 })
    expect(namn('2026-06-18')).toBeNull()
    expect(namn('2026-06-19')).toBe('midsommar')
    expect(namn('2026-06-20')).toBe('midsommar')
    expect(namn('2026-06-21')).toBeNull()
    expect(namn('2027-06-25')).toBe('midsommar')
    expect(namn('2027-06-26')).toBe('midsommar')
  })

  test('valdagen: andra söndagen i september valåren, med länk till val.se', () => {
    expect(valdagen(2026)).toEqual({ ar: 2026, manad: 9, dag: 13 })
    expect(valdagen(2027)).toBeNull()
    expect(valdagen(2030)).toEqual({ ar: 2030, manad: 9, dag: 8 })
    const t = temaFor('2026-09-13')
    expect(t?.namn).toBe('valdagen')
    expect(t?.text).toBe('I dag är det val')
    expect(t?.lank?.href).toBe('https://www.val.se/')
    expect(namn('2026-09-12')).toBeNull()
    expect(namn('2027-09-12')).toBeNull()
  })

  test('Härnösands dag 11 mars: antal år sedan 1585 och källan som tooltip', () => {
    const t = temaFor('2026-03-11')
    expect(t?.namn).toBe('harnosandsdag')
    expect(t?.text).toBe('Härnösand fick sina stadsprivilegier i dag för 441 år sedan (1585)')
    expect(t?.symbol).toBe('vagen')
    expect(t?.tooltip).toBe(
      'Den 11 mars 1585 fick Härnösand sina stadsprivilegier av Johan III. Det är den dag som brukar firas.',
    )
    expect(text('2030-03-11')).toContain('445 år sedan')
    expect(namn('2026-03-12')).toBeNull()
    expect(namn('2026-09-14')).toBeNull()
  })

  test('nedräkningen de 30 dagarna före Härnösands dag, med skottår', () => {
    expect(namn('2026-02-08')).toBeNull()
    expect(temaFor('2026-02-09')).toEqual({
      namn: 'nedrakning',
      text: '30 dagar kvar till Härnösands dag – 441 år sedan stadsprivilegierna',
      symbol: null,
    })
    expect(text('2026-03-01')).toBe('10 dagar kvar till Härnösands dag – 441 år sedan stadsprivilegierna')
    expect(text('2026-03-09')).toBe('2 dagar kvar till Härnösands dag – 441 år sedan stadsprivilegierna')
    expect(text('2026-03-10')).toBe('I morgon är det Härnösands dag')
    // 2028 är skottår: nedräkningen börjar den 10 februari.
    expect(namn('2028-02-09')).toBeNull()
    expect(text('2028-02-10')).toBe('30 dagar kvar till Härnösands dag – 443 år sedan stadsprivilegierna')
  })

  test('gränsdagar för jul, lucia och nyår', () => {
    expect(namn('2026-12-12')).toBeNull()
    expect(namn('2026-12-13')).toBe('lucia')
    expect(namn('2026-12-14')).toBeNull()
    expect(namn('2026-12-23')).toBeNull()
    expect(namn('2026-12-24')).toBe('jul')
    expect(namn('2026-12-25')).toBe('jul')
    expect(namn('2026-12-26')).toBe('jul')
    expect(namn('2026-12-27')).toBeNull()
    expect(namn('2026-12-30')).toBeNull()
    expect(namn('2026-12-31')).toBe('nyar')
    expect(namn('2027-01-01')).toBe('nyar')
    expect(namn('2027-01-02')).toBeNull()
    expect(temaFor('2026-12-24')).toEqual({ namn: 'jul', text: 'God jul', symbol: 'stjarnan' })
  })

  test('nationaldagen', () => {
    expect(temaFor('2026-06-06')).toEqual({ namn: 'nationaldagen', text: 'Sveriges nationaldag', symbol: 'flagga' })
    expect(namn('2026-06-05')).toBeNull()
  })

  test('vanliga dagar och politiskt laddade dagar har inget tema', () => {
    for (const d of ['2026-11-24', '2026-11-29', '2026-05-01', '2026-11-01', '2026-07-15']) {
      expect(temaFor(d), d).toBeNull()
    }
  })

  test('internationella kvinnodagen får inget eget tema, bara nedräkningen', () => {
    expect(namn('2026-03-08')).toBe('nedrakning')
  })

  test('räknar i svensk tid', () => {
    // 23:30 UTC den 23 december är 00:30 den 24 december i Sverige.
    expect(temaFor(new Date('2026-12-23T23:30:00Z'))?.namn).toBe('jul')
    // 22:30 UTC den 26 december är 23:30 samma dag i Sverige, fortfarande jul.
    expect(temaFor(new Date('2026-12-26T22:30:00Z'))?.namn).toBe('jul')
    expect(temaFor(new Date('2026-12-26T23:30:00Z'))).toBeNull()
  })
})
