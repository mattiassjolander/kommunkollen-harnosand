import { expect, test } from '@playwright/test'
import { API_PORT } from '../playwright.config'

// Sökningen (#142): sökrutan i sidhuvudet, sidan Sök, filter och länkar till träffarna.
test.beforeAll(async ({ request }) => {
  test.setTimeout(180_000) // insamlingen tolkar ett femtiotal protokoll och bygger sökindexet
  const api = `http://127.0.0.1:${API_PORT}`
  expect((await request.post(`${api}/api/auth/test/redaktor`)).ok()).toBeTruthy()
  expect((await request.post(`${api}/api/insamlingar`)).ok()).toBeTruthy()
})

test('sökrutan leder till sidan Sök, med filter, markeringar och länkar till träffen', async ({ page }) => {
  await page.goto('/')
  const ruta = page.getByRole('search', { name: 'Sök på plattformen' })
  await ruta.getByTestId('sokruta').fill('frågestund')
  await ruta.getByTestId('sokruta').press('Enter')

  await expect(page).toHaveURL(/\/sok\?q=fr%C3%A5gestund$/)
  await expect(page.getByRole('heading', { name: 'Sök', level: 1 })).toBeVisible()
  await expect(page.getByTestId('antal-traffar')).toContainText('träffar för ”frågestund”')
  await expect(page.getByTestId('traff').first()).toBeVisible()
  // Frågan står kvar i sidhuvudets ruta.
  await expect(ruta.getByTestId('sokruta')).toHaveValue('frågestund')

  // Antalet per typ är filter.
  const typer = page.getByTestId('typfilter')
  await expect(typer.locator('[data-typ="behandling"]')).toContainText(/Behandlingar \d+/)
  await expect(typer.locator('[data-typ="protokollsida"]')).toContainText(/Protokollsidor \d+/)
  await typer.locator('[data-typ="behandling"]').click()
  await expect(page).toHaveURL(/typ=behandling/)
  await expect(typer.locator('[data-typ="behandling"]')).toHaveAttribute('aria-pressed', 'true')
  await expect(page.locator('[data-testid="traff"]:not([data-typ="behandling"])')).toHaveCount(0)

  await page.getByTestId('filter-organ').selectOption('KF')
  await expect(page).toHaveURL(/organ=KF/)
  await page.getByTestId('filter-ar').selectOption('2026')
  await expect(page).toHaveURL(/ar=2026/)
  await page.getByTestId('sortering').selectOption('datum')
  await expect(page).toHaveURL(/sortering=datum/)
  const forsta = page.getByTestId('traff').first()
  await expect(forsta).toContainText('Kommunfullmäktige')
  await expect(forsta).toContainText('2026')
  await expect(forsta.getByTestId('automatiskt-tolkad')).toBeVisible()
  // Länken till PDF:en går till sidan där paragrafen står.
  await expect(forsta.getByTestId('traff-pdf')).toHaveAttribute('href', /^\/api\/dokument\/\d+#page=\d+$/)

  await forsta.getByTestId('traff-lank').click()
  await expect(page).toHaveURL(/\/politik\/sammantraden\/\d+\/paragraf\/\d+$/)
  await expect(page.getByRole('heading', { level: 1 })).toContainText('frågestund')
})

test('protokollens text, utdrag med markerade sökord och ett ledamotsnamn överst', async ({ page }) => {
  await page.goto('/sok?q=Lennart%20Molin')
  const forsta = page.getByTestId('traff').first()
  await expect(forsta).toHaveAttribute('data-typ', 'ledamot')
  await expect(forsta.getByTestId('traff-lank')).toHaveText('Lennart Molin')

  await page.getByTestId('typfilter').locator('[data-typ="protokollsida"]').click()
  const sida = page.getByTestId('traff').first()
  await expect(sida.locator('mark').first()).toBeVisible()
  await expect(sida.getByTestId('traff-pdf')).toHaveAttribute('href', /^\/api\/dokument\/\d+#page=\d+$/)
  await sida.getByTestId('traff-lank').click()
  await expect(page).toHaveURL(/\/politik\/sammantraden\/\d+$/)
})

test('vyn Datakällor visar hur många sökbara enheter som har vektorer (#69)', async ({ page }) => {
  await page.goto('/datakallor')
  const s = page.getByTestId('sokvektorer')
  await expect(s.getByRole('heading', { name: 'Sökningen' })).toBeVisible()
  await expect(s).toContainText(/[\d\s]+ av [\d\s]+ sökbara enheter har vektorer för sökning på betydelse, och 0 väntar/)
})

test('sidan Sök i mobilbredd och mörkt läge', async ({ page }) => {
  await page.setViewportSize({ width: 375, height: 812 })
  await page.emulateMedia({ colorScheme: 'dark' })
  await page.goto('/sok?q=budget')
  await expect(page.getByTestId('traff').first()).toBeVisible()
  await expect(page.getByTestId('sokruta')).toBeVisible()
  const bredd = await page.evaluate(() => document.documentElement.scrollWidth)
  expect(bredd).toBeLessThanOrEqual(375)
})
