import { expect, test, type Page } from '@playwright/test'
import { API_PORT } from '../playwright.config'

// Protokollsammanställning (#195): kortet på sammanträdessidan och raden i sammanträdeslistan.
const api = `http://127.0.0.1:${API_PORT}`

test.beforeAll(async ({ request }) => {
  test.setTimeout(300_000) // insamlingen tolkar protokollen
  expect((await request.post(`${api}/api/auth/test/redaktor`)).ok()).toBeTruthy()
  for (const kalla of ['harnosand-protokoll-ks', 'harnosand-protokoll-kf']) {
    expect((await request.post(`${api}/api/insamlingar?kalla=${kalla}`)).ok()).toBeTruthy()
  }
  expect((await request.post(`${api}/api/auth/logga-ut`)).ok()).toBeTruthy()
})

async function kf20260223(page: Page) {
  await page.goto('/politik?organ=KF')
  await page.locator('[data-testid="sammantrade"][data-datum="2026-02-23"]').getByRole('rowheader').getByRole('link').click()
  await expect(page.getByTestId('sammanstallning')).toBeVisible()
}

test('kortet har talen, och ett tal visar bara sina paragrafer med filtret i URL:en', async ({ page }) => {
  await kf20260223(page)
  const kort = page.getByTestId('sammanstallning')
  // Samma markering som protokollet (#176).
  await expect(kort.getByTestId('sammanstallning-automatiskt-tolkad')).toContainText('Automatiskt tolkad, ej granskad')
  await expect(kort.getByTestId('tal-arenden')).toContainText('5ärenden av 14 paragrafer')
  await expect(kort.getByTestId('tal-beslut')).toContainText('5beslut')
  await expect(kort.getByTestId('tal-forslag_vidare')).toContainText('0förslag vidare')
  await expect(kort.getByTestId('tal-oenighet')).toContainText('1med oenighet')

  // Oenighet: voteringar och reservationer med partierna som förkortningar, utan partifärg.
  const oenighet = kort.getByTestId('rad-oenighet')
  await expect(oenighet.getByTestId('chip-votering')).toHaveText('Votering · 1')
  await expect(oenighet.getByTestId('chip-reservation')).toContainText(/Reservation · 2 \(([A-Z]+, )*SD(, [A-Z]+)*\)/)
  await expect(kort.getByTestId('rad-beslutsgang')).toContainText('1 ny motion')
  await expect(kort.getByTestId('rad-beslutsgang')).toContainText('1 ny interpellation')
  await expect(kort.getByTestId('rad-sammantradet')).toContainText('1 h 55 min')
  await expect(kort.getByTestId('rad-sammantradet')).toContainText('beslutande')

  // Ett klick på talet visar bara de paragraferna, och filtret speglas i URL:en.
  await expect(page.getByTestId('behandling')).toHaveCount(14)
  await kort.getByTestId('tal-arenden').click()
  await expect(page).toHaveURL(/visa=arenden/)
  await expect(page.getByTestId('behandling')).toHaveCount(5)
  await expect(kort.getByTestId('tal-arenden')).toHaveAttribute('aria-pressed', 'true')
  await expect(page.getByTestId('antal-visade')).toContainText('5 av 14 behandlingar: ärenden')

  await oenighet.getByTestId('chip-votering').click()
  await expect(page).toHaveURL(/visa=votering/)
  await expect(page.getByTestId('behandling')).toHaveCount(1)
  await expect(page.getByTestId('behandling')).toHaveAttribute('data-paragraf', '5')

  // Länken går att dela: filtret finns kvar när sidan laddas om.
  await page.reload()
  await expect(page.getByTestId('behandling')).toHaveCount(1)
  await page.getByTestId('visa-alla').click()
  await expect(page).not.toHaveURL(/visa=/)
  await expect(page.getByTestId('behandling')).toHaveCount(14)
})

test('Skickas vidare och kallelsens punkter som inte behandlades', async ({ page, request }) => {
  const lista = await (await request.get(`${api}/api/sammantraden?organ=KS`)).json()
  const ks = lista.find((s: { sammanstallning: { forslag_vidare: number } | null }) => s.sammanstallning?.forslag_vidare)
  test.skip(!ks, 'inget sammanträde med förslag vidare')
  // Kallelsens avvikelser (#121) kommer från kallelserna, som inte samlas in här. En punkt läggs till i svaret.
  await page.route(new RegExp(`/api/sammantraden/${ks.id}$`), async (route) => {
    const svar = await route.fetch()
    const data = await svar.json()
    data.sammanstallning.kallelsen.ej_behandlade = [
      {
        rubrik: 'Bidrag till föreningen X',
        text: 'Kallelse, sidan 3: punkten "Bidrag till föreningen X" behandlas inte i protokollet.',
        lank: { titel: 'Kallelse', url: 'https://harnosand.se/kallelse.pdf#page=3', sida: 3 },
      },
    ]
    await route.fulfill({ response: svar, json: data })
  })
  await page.goto(`/politik/sammantraden/${ks.id}`)
  const vidare = page.getByTestId('skickas-vidare')
  await expect(vidare.getByRole('heading', { level: 3 }).first()).toContainText('Skickas vidare till')
  await expect(vidare.getByRole('listitem')).toHaveCount(ks.sammanstallning.forslag_vidare)
  await expect(vidare.getByRole('link', { name: 'Se dem i Kommande ärenden ›' })).toHaveAttribute('href', '/politik/kommande')
  const kallelsen = page.getByTestId('kallelsen-mot-protokollet')
  await expect(kallelsen).toContainText('1 punkt i kallelsen behandlades inte')
  await expect(kallelsen.getByRole('link', { name: 'Bidrag till föreningen X' })).toHaveAttribute(
    'href',
    'https://harnosand.se/kallelse.pdf#page=3',
  )
  await expect(kallelsen).toContainText('sidan 3 i kallelsen')

  await page.getByTestId('tal-forslag_vidare').click()
  await expect(page.getByTestId('behandling')).toHaveCount(ks.sammanstallning.forslag_vidare)
})

test('listan har den kompakta raden, chips, organfärg och märkningsfilter i URL:en', async ({ page }) => {
  await page.goto('/politik?organ=KF')
  const rad = page.locator('[data-testid="sammantrade"][data-datum="2026-02-23"]')
  const sammanstallning = rad.getByTestId('sammanstallning')
  await expect(sammanstallning).toContainText('5 ärenden·5 beslut')
  await expect(sammanstallning).not.toContainText('förslag vidare')
  await expect(sammanstallning.getByTestId('chip')).toHaveText(['Votering', 'Reservation · 2', 'Oenighet'])
  await expect(rad.getByTestId('organnamn')).toHaveCSS('border-left-style', 'solid')
  await expect(page.getByRole('columnheader', { name: 'Behandlingar' })).toHaveCount(0)

  // Ett sammanträde utan oenighet är "Enigt".
  await expect(page.getByTestId('enigt').first()).toHaveText('Enigt')

  const alla = await page.getByTestId('sammantrade').count()
  await page.getByTestId('markningsfilter').selectOption('votering')
  await expect(page).toHaveURL(/markning=votering/)
  await expect.poll(() => page.getByTestId('sammantrade').count()).toBeLessThan(alla)
  const rader = page.getByTestId('sammantrade')
  await expect
    .poll(() => rader.evaluateAll((el) => el.length > 0 && el.every((e) => e.querySelector('[data-markning="votering"]'))))
    .toBe(true)
  await page.reload()
  await expect(page.getByTestId('markningsfilter')).toHaveValue('votering')
})

test('ett protokoll som inte kunde tolkas: streck i listan och ingen sammanställning på sidan', async ({ page }) => {
  const otolkat = async (route: import('@playwright/test').Route) => {
    const svar = await route.fetch()
    const data = await svar.json()
    for (const s of Array.isArray(data) ? data.slice(0, 1) : [data]) {
      s.tolkning = 'ej_tolkad'
      s.sammanstallning = null
    }
    await route.fulfill({ response: svar, json: data })
  }
  await page.route(/\/api\/sammantraden(\?.*)?$/, otolkat)
  await page.route(/\/api\/sammantraden\/\d+$/, otolkat)
  await page.goto('/politik')
  await expect(page.getByTestId('sammantrade').first().getByTestId('ingen-sammanstallning')).toHaveText('–')
  await page.getByTestId('sammantrade').first().getByRole('rowheader').getByRole('link').click()
  await expect(page.getByTestId('ingen-sammanstallning')).toHaveText(
    'Ingen sammanställning: protokollet kunde inte tolkas automatiskt.',
  )
  await expect(page.getByTestId('sammanstallning').getByRole('button')).toHaveCount(0)
})

// WCAG-kontrast mellan två färger som getComputedStyle ger dem, "rgb(r, g, b)".
function kontrast(a: string, b: string): number {
  const lum = (c: string) => {
    const [r, g, bl] = (c.match(/\d+(\.\d+)?/g) ?? []).slice(0, 3).map((x) => {
      const v = Number(x) / 255
      return v <= 0.04045 ? v / 12.92 : ((v + 0.055) / 1.055) ** 2.4
    })
    return 0.2126 * r + 0.7152 * g + 0.0722 * bl
  }
  const [hi, lo] = [lum(a), lum(b)].sort((x, y) => y - x)
  return (hi + 0.05) / (lo + 0.05)
}

for (const lage of ['light', 'dark'] as const) {
  test(`kortet och listan i ${lage === 'light' ? 'ljust' : 'mörkt'} läge`, async ({ page }) => {
    await page.emulateMedia({ colorScheme: lage })
    await page.goto('/politik?organ=KF')
    const chips = page.locator('[data-testid="sammantrade"][data-datum="2026-02-23"]').getByTestId('chip')
    await expect(chips).toHaveCount(3)
    for (const c of await chips.all()) {
      const f = await c.evaluate((e) => ({ fg: getComputedStyle(e).color, bg: getComputedStyle(e).backgroundColor }))
      expect(kontrast(f.fg, f.bg), `${lage}: ${f.fg} på ${f.bg}`).toBeGreaterThanOrEqual(4.5)
    }
    await page.screenshot({ path: `test-results/sammantradeslista-${lage}.png`, fullPage: false })

    await kf20260223(page)
    const kort = page.getByTestId('sammanstallning')
    const farger = await kort.evaluate((e) => {
      const s = getComputedStyle(e)
      const tal = getComputedStyle(e.querySelector('.tal .v')!)
      const etikett = getComputedStyle(e.querySelector('.tal .e')!)
      const ruta = getComputedStyle(e.querySelector('.tal')!)
      return { kort: s.backgroundColor, tal: tal.color, etikett: etikett.color, ruta: ruta.backgroundColor }
    })
    // Talen och etiketterna går att läsa mot rutan, och rutan skiljer sig från kortet.
    expect(kontrast(farger.tal, farger.ruta)).toBeGreaterThanOrEqual(4.5)
    expect(kontrast(farger.etikett, farger.ruta)).toBeGreaterThanOrEqual(4.5)
    expect(farger.ruta).not.toBe(farger.kort)
    for (const c of await kort.locator('.chip').all()) {
      const f = await c.evaluate((e) => ({ fg: getComputedStyle(e).color, bg: getComputedStyle(e).backgroundColor }))
      expect(kontrast(f.fg, f.bg), `${lage}: ${f.fg} på ${f.bg}`).toBeGreaterThanOrEqual(4.5)
    }
    await kort.screenshot({ path: `test-results/sammanstallning-${lage}.png` })
  })
}

test('ett granskat protokoll: kortet har samma markering som protokollet (#176)', async ({ page }) => {
  await page.route(/\/api\/sammantraden\/\d+$/, async (route) => {
    const svar = await route.fetch()
    const data = await svar.json()
    data.granskad = '2026-11-27'
    await route.fulfill({ response: svar, json: data })
  })
  await kf20260223(page)
  await expect(page.getByTestId('granskat-protokoll')).toContainText('Granskad av redaktionen 2026-11-27')
  await expect(page.getByTestId('sammanstallning').getByTestId('sammanstallning-granskat-protokoll')).toContainText(
    'Granskad av redaktionen 2026-11-27',
  )
})
