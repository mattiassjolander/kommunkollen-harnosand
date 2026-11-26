import { expect, test } from '@playwright/test'
import { API_PORT } from '../playwright.config'

// Rankningar (#66): Svenskt Näringslivs lokala företagsklimat och Aktuell Hållbarhets miljöbästa kommun, från de
// inspelade källsvaren.

const api = `http://127.0.0.1:${API_PORT}`

test.beforeAll(async ({ request }) => {
  test.setTimeout(180_000) // insamlingen tolkar ett femtiotal protokoll
  expect((await request.post(`${api}/api/auth/test/redaktor`)).ok()).toBeTruthy()
  expect((await request.post(`${api}/api/insamlingar`)).ok()).toBeTruthy()
})

test('översikten har en ruta per rankning med placering, förändring och avsändare', async ({ page }) => {
  await page.goto('/')
  // Gruppen Kommunen i jämförelse leder till sin första undervy, Rankningar (#160).
  await page.getByRole('navigation', { name: 'Huvudvyer' }).getByRole('link', { name: 'Kommunen i jämförelse' }).click()
  await expect(page).toHaveURL(/\/rankningar$/)
  await expect(page.getByRole('heading', { name: 'Rankningar', level: 1 })).toBeVisible()
  await expect(page.getByTestId('anvandare').getByRole('button', { name: 'Logga in' })).toBeVisible()

  const kort = page.getByTestId('rankningskort')
  await expect(kort).toHaveCount(2)
  const fk = kort.filter({ hasText: 'Lokalt företagsklimat' })
  await expect(fk).toContainText('Svenskt Näringsliv · Arbetsgivar- och näringslivsorganisation')
  await expect(fk.getByTestId('placering')).toHaveText('Plats 265 av 290')
  await expect(fk.getByTestId('forandring')).toContainText('2025: plats 283')
  await expect(fk.getByTestId('forandring')).toContainText('Förändring i placering: −18')

  const mb = kort.filter({ hasText: 'Sveriges miljöbästa kommun' })
  await expect(mb).toContainText('Aktuell Hållbarhet · Tidning om miljö och hållbarhet')
  await expect(mb.getByTestId('placering')).toHaveText('Plats 52 av 290')
  await expect(mb).toContainText('16,8 av 33,5 poäng')
  await expect(mb.getByTestId('forandring')).toContainText('2025: plats 69')

  // Inga värderande ord.
  await expect(page.locator('main')).not.toContainText(/förbättr|försämr|bättre|sämre/i)
})

test('sidan per rankning visar placeringen över tid, delmåtten mot riket och texten om avsändaren', async ({ page }) => {
  await page.goto('/rankningar')
  await page.getByTestId('rankningskort').filter({ hasText: 'Lokalt företagsklimat' }).click()
  await expect(page.getByRole('heading', { name: 'Lokalt företagsklimat', level: 1 })).toBeVisible()
  await expect(page.getByTestId('avsandare')).toContainText('En rankning av Svenskt Näringsliv')

  // Diagrammet med Härnösand och grannkommunerna.
  const diagram = page.getByRole('img', { name: /placering per år för Härnösand och grannkommunerna/ })
  await expect(diagram).toBeVisible()
  const forklaring = page.getByRole('list', { name: 'Teckenförklaring' })
  for (const kommun of ['Härnösand', 'Sundsvall', 'Kramfors', 'Timrå', 'Sollefteå', 'Örnsköldsvik']) {
    await expect(forklaring).toContainText(kommun)
  }
  await expect(page.getByTestId('kallrad').first()).toContainText('Källa: Svenskt Näringsliv')

  // Tabellvyn.
  await page.getByTestId('visa-tabell').click()
  const rad2026 = page.getByTestId('placeringstabell').getByRole('row').filter({ hasText: '2026' })
  await expect(rad2026.getByRole('cell').first()).toHaveText('265')

  // Delmåtten mot riket.
  const omdome = page
    .getByTestId('delmatt')
    .getByRole('row')
    .filter({ hasText: 'Vilket sammanfattande omdöme vill du ge företagsklimatet i kommunen?' })
  await expect(omdome).toContainText('3,18')
  await expect(omdome).toContainText('3,53')

  const om = page.getByTestId('om-rankningen')
  await expect(om).toContainText('arbetsgivar- och näringslivsorganisation')
  await expect(om).toContainText('källan ska alltid anges')
  await expect(om.getByRole('link', { name: /beskrivning av metoden/ })).toHaveAttribute(
    'href',
    'https://www.foretagsklimat.se/om-foretagsklimat/metod-for-rankingen/',
  )
  // Inga värderande ord i plattformens egna texter (källans frågor återges som de är).
  for (const text of [page.getByTestId('avsandare'), om, ...(await page.locator('.forklaring').all())]) {
    await expect(text).not.toContainText(/förbättr|försämr|bättre|sämre/i)
  }
})

test('miljörankningen visar poängen per indikator för det senaste året', async ({ page }) => {
  await page.goto('/rankningar/miljobasta-kommun')
  await expect(page.getByRole('heading', { name: 'Sveriges miljöbästa kommun', level: 1 })).toBeVisible()
  await expect(page.getByTestId('avsandare')).toContainText('plats 52 av 290, 16,8 av 33,5 poäng')
  const delmatt = page.getByTestId('delmatt')
  await expect(delmatt.getByRole('row').filter({ hasText: 'PFOS/PFAS' })).toContainText('Nej (0 p)')
  await expect(delmatt.getByRole('row').filter({ hasText: 'Ekologiska livsmedel' })).toContainText('0,42 p')
  await expect(page.getByTestId('om-rankningen')).toContainText('Inga användarvillkor har hittats')
})

test('en redaktör registrerar ett metodbyte som bryter linjen i diagrammet', async ({ page }) => {
  await page.goto('/rankningar/miljobasta-kommun')
  await expect(page.getByTestId('metodbyte')).toHaveCount(0)
  await page.request.post('/api/auth/test/redaktor')
  await page.goto('/rankningar/miljobasta-kommun')

  const metodbyten = page.getByTestId('metodbyten')
  await metodbyten.getByLabel('År').fill('2016')
  await metodbyten.getByLabel('Vad ändrades i metoden').fill('Klimatdata blev ett eget område')
  await metodbyten.getByRole('button', { name: 'Registrera metodbyte' }).click()
  await expect(metodbyten).toContainText('2016: Klimatdata blev ett eget område')
  await expect(page.getByTestId('metodbyte')).toHaveCount(1)
  await expect(page.getByTestId('metodbyte')).toContainText('Metodbyte 2016')

  await metodbyten.getByRole('button', { name: 'Ta bort' }).click()
  await expect(page.getByTestId('metodbyte')).toHaveCount(0)
})

// #177: förändringen mot föregående år visas med ▲, ▼ eller = framför texten, i den divergerande paletten.

/** Färgen som en token ger i det aktuella läget, för jämförelse med ikonens beräknade färg. */
async function tokenfarg(page: import('@playwright/test').Page, token: string): Promise<string> {
  return page.evaluate((t) => {
    const prov = document.createElement('span')
    prov.style.color = `var(${t})`
    document.body.append(prov)
    const farg = getComputedStyle(prov).color
    prov.remove()
    return farg
  }, token)
}

for (const lage of ['light', 'dark'] as const) {
  test(`rankningskorten har ikon och färg för förändringen (${lage === 'light' ? 'ljust' : 'mörkt'} läge)`, async ({
    page,
  }) => {
    await page.emulateMedia({ colorScheme: lage })
    // Placeringarna i de inspelade källsvaren förbättras båda, så de andra fallen läggs in i svaret.
    await page.route('**/api/rankningar', async (route) => {
      const svar = await route.fetch()
      const rankningar = await svar.json()
      const mall = rankningar[0]
      const variant = (id: string, titel: string, foregaende: number | null) => ({
        ...mall,
        id,
        titel,
        senaste: {
          ...mall.senaste,
          placering: 100,
          foregaende: foregaende === null ? null : { ar: mall.senaste.ar - 1, placering: foregaende },
          andring: foregaende === null ? null : 100 - foregaende,
          metodbyte: false,
        },
      })
      await route.fulfill({
        response: svar,
        json: [
          ...rankningar,
          variant('lagre', 'Exempel högre platsnummer', 90),
          variant('samma', 'Exempel samma plats', 100),
          variant('utan', 'Exempel utan föregående år', null),
        ],
      })
    })
    await page.goto('/rankningar')
    const kort = page.getByTestId('rankningskort')

    const fk = kort.filter({ hasText: 'Lokalt företagsklimat' })
    const upp = fk.getByTestId('placeringsikon')
    await expect(upp).toHaveText('▲')
    await expect(upp).toHaveAttribute('aria-hidden', 'true')
    await expect(fk.getByTestId('forandring')).toContainText('Förändring i placering: −18')
    await expect(upp).toHaveCSS('color', await tokenfarg(page, '--diverg-hogre'))

    const ned = kort.filter({ hasText: 'Exempel högre platsnummer' })
    await expect(ned.getByTestId('placeringsikon')).toHaveText('▼')
    await expect(ned.getByTestId('placeringsikon')).toHaveCSS('color', await tokenfarg(page, '--diverg-lagre'))
    await expect(ned.getByTestId('forandring')).toContainText('Förändring i placering: +10')

    const samma = kort.filter({ hasText: 'Exempel samma plats' })
    await expect(samma.getByTestId('placeringsikon')).toHaveText('=')
    await expect(samma.getByTestId('placeringsikon')).toHaveCSS('color', await tokenfarg(page, '--ink-muted'))
    await expect(samma.getByTestId('forandring')).toContainText('Samma placering')

    const utan = kort.filter({ hasText: 'Exempel utan föregående år' })
    await expect(utan.getByTestId('placering')).toHaveText('Plats 100 av 290')
    await expect(utan.getByTestId('placeringsikon')).toHaveCount(0)
  })
}

test('delmåtten har ikon för förändringen i placering, och ingen pil vid metodbyte', async ({ page }) => {
  await page.goto('/rankningar/foretagsklimat')
  const omdome = page
    .getByTestId('delmatt')
    .getByRole('row')
    .filter({ hasText: 'Vilket sammanfattande omdöme vill du ge företagsklimatet i kommunen?' })
  // Plats 236 mot 263 året innan.
  await expect(omdome.getByTestId('delmattsforandring')).toContainText('plats −27 (mot 2025)')
  await expect(omdome.getByTestId('placeringsikon')).toHaveText('▲')
  await expect(omdome.getByTestId('placeringsikon')).toHaveCSS('color', await tokenfarg(page, '--diverg-hogre'))
  // Varje delmått med placering båda åren har en ikon.
  const ikoner = page.getByTestId('delmatt').getByTestId('placeringsikon')
  expect(await ikoner.count()).toBeGreaterThan(1)

  // Ett metodbyte mellan 2025 och 2026: "Ny metod" och ingen pil, på delmåtten och på kortet.
  await page.request.post('/api/auth/test/redaktor')
  await page.goto('/rankningar/foretagsklimat')
  const metodbyten = page.getByTestId('metodbyten')
  await metodbyten.getByLabel('År').fill('2026')
  await metodbyten.getByLabel('Vad ändrades i metoden').fill('Ny enkät')
  await metodbyten.getByRole('button', { name: 'Registrera metodbyte' }).click()
  await expect(metodbyten).toContainText('2026: Ny enkät')
  await expect(omdome.getByTestId('delmattsforandring')).toHaveText('Ny metod')
  await expect(omdome.getByTestId('placeringsikon')).toHaveCount(0)

  await page.goto('/rankningar')
  const fk = page.getByTestId('rankningskort').filter({ hasText: 'Lokalt företagsklimat' })
  await expect(fk.getByTestId('forandring')).toHaveText('2025: plats 283 · Ny metod')
  await expect(fk.getByTestId('placeringsikon')).toHaveCount(0)

  await page.goto('/rankningar/foretagsklimat')
  await page.getByTestId('metodbyten').getByRole('button', { name: 'Ta bort' }).click()
  await expect(page.getByTestId('metodbyten')).not.toContainText('2026: Ny enkät')
  await expect(omdome.getByTestId('placeringsikon')).toHaveText('▲')
})
