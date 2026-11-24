import { expect, test } from '@playwright/test'
import { API_PORT } from '../playwright.config'

test.beforeAll(async ({ request }) => {
  test.setTimeout(180_000) // insamlingen tolkar ett femtiotal protokoll
  const api = `http://127.0.0.1:${API_PORT}`
  expect((await request.post(`${api}/api/auth/test/redaktor`)).ok()).toBeTruthy()
  expect((await request.post(`${api}/api/insamlingar`)).ok()).toBeTruthy()
})

test('översikten renderar stat-kort med värde, förändring och källa', async ({ page }) => {
  await page.goto('/')
  await expect(page.getByRole('heading', { name: 'Översikt', level: 1 })).toBeVisible()
  const kort = page.getByTestId('statkort')
  await expect(kort).toHaveCount(8)

  const resultat = page.locator('[data-testid="statkort"][data-matt="scb:ResultKnN:120"]')
  await expect(resultat.getByRole('heading')).toContainText('Årets resultat')
  await expect(resultat.getByTestId('statvarde')).toContainText(/^−?[\d ]+,\d mnkr$/)
  await expect(resultat).toContainText('2025')
  await expect(resultat.getByTestId('statforandring')).toContainText(/[+−][\d ]+,\d mnkr\s*\([+−][\d ]+,\d %\)\s*mot 2024/)
  await expect(resultat.getByTestId('kallrad')).toContainText('Källa: SCB (ResultKnN, post 120)')

  // Nyckeltal i procent: förändringen i procentenheter.
  const soliditet = page.locator('[data-testid="statkort"][data-matt="kolada:N03106"]')
  await expect(soliditet.getByTestId('statforandring')).toContainText('procentenheter')
  await expect(soliditet.getByTestId('kallrad')).toContainText('Kolada (N03106)')
})

test('översikten visar datainsamlingens status: senaste och nästa uppdatering och källstatus', async ({ page }) => {
  await page.goto('/')
  const status = page.getByTestId('statuspanel')
  await expect(status).toContainText('Fullständigt uppdaterad')
  await expect(status.getByTestId('senaste-insamling')).toContainText(/\d{1,2} [a-zä]+ \d{4}, \d{2}:\d{2}/)
  await expect(status.getByTestId('nasta-insamling')).toContainText(/(1|15) [a-zä]+ \d{4}, 03:00/)
  await expect(status.getByTestId('kallstatus')).toContainText('10 av 10 kontrollerade utan fel')
})

test('genvägarna leder till rätt vyer', async ({ page }) => {
  for (const [namn, url, rubrik] of [
    ['Ekonomi', '/ekonomi', 'Ekonomi'],
    ['Ekonomiska flöden – Sankey', '/floden', 'Ekonomiska flöden'],
    ['Datakällor', '/datakallor', 'Datakällor och uppdateringsstatus'],
  ]) {
    await page.goto('/')
    await page.getByTestId('genvagar').getByRole('link', { name: new RegExp(`^${namn} ›`) }).click()
    await expect(page).toHaveURL(new RegExp(`${url}$`))
    await expect(page.getByRole('heading', { name: rubrik, level: 1 })).toBeVisible()
  }

  // Ett stat-kort leder till nyckeltalets grupp i ekonomivyn.
  await page.goto('/')
  await page.locator('[data-testid="statkort"][data-matt="kolada:N03106"]').getByRole('link').first().click()
  await expect(page).toHaveURL(/\/ekonomi#stallning$/)
  await expect(page.locator('#stallning')).toBeInViewport()
})
