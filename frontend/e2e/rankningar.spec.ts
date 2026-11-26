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
