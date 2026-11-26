import { expect, test } from '@playwright/test'
import { API_PORT } from '../playwright.config'

test.beforeAll(async ({ request }) => {
  test.setTimeout(180_000) // insamlingen tolkar ett femtiotal protokoll
  const api = `http://127.0.0.1:${API_PORT}`
  expect((await request.post(`${api}/api/auth/test/redaktor`)).ok()).toBeTruthy()
  // Två körningar: den första hämtar uppgifterna, den andra hittar inget nytt.
  for (let i = 0; i < 2; i++) expect((await request.post(`${api}/api/insamlingar`)).ok()).toBeTruthy()
})

test('statusindikatorn syns i sidhuvudet på alla sidor', async ({ page }) => {
  for (const sida of ['/ekonomi', '/datakallor']) {
    await page.goto(sida)
    const indikator = page.getByTestId('statusindikator')
    await expect(indikator).toContainText('Fullständigt uppdaterad')
    await expect(indikator).toContainText('Senaste insamling:')
    await expect(indikator).toContainText('Senast lyckad:')
    await expect(indikator.getByTestId('nasta-korning')).toContainText(/Nästa insamling: (1|15) [a-zä]+ \d{4}, 03:00/)
    await expect(indikator).toContainText('13 av 13 kontrollerade utan fel') // Kolada, SCB, SKR, protokollen från fem organ, sammanträdesplanerna, de styrande dokumenten, Valmyndigheten och två rankningar
  }
})

test('vyn Datakällor visar status per källa och körningsloggen', async ({ page }) => {
  await page.goto('/ekonomi')
  // Datakällor står under den diskreta raden Om Kommunkollen (#160).
  await page.getByRole('navigation', { name: 'Huvudvyer' }).getByRole('link', { name: 'Om Kommunkollen' }).click()
  await expect(page.getByRole('heading', { name: 'Datakällor och uppdateringsstatus' })).toBeVisible()

  const kolada = page.getByTestId('datakallor').locator('tr[data-kalla="kolada"]')
  await expect(kolada).toContainText('Kolada')
  await expect(kolada).toContainText('2026-08-28') // senaste publicerade uppgift enligt källan
  await expect(kolada.getByTestId('status')).not.toHaveAttribute('data-status', 'aldrig')

  // Den senaste körningen hittade inget nytt, en tidigare hämtade uppgifterna.
  const logg = page.getByTestId('korningslogg')
  await expect(logg.locator('tbody.korning').first()).toContainText('Inga nya uppgifter')
  await expect(logg).toContainText('Lyckad')
})

test('en redaktör kan köra om en enskild källa från vyn Datakällor', async ({ page }) => {
  await page.goto('/datakallor')
  // Läsare utan inloggning ser ingen knapp.
  await expect(page.getByTestId('datakallor')).toBeVisible()
  await expect(page.getByTestId('kor-om-scb')).toHaveCount(0)

  await page.request.post('/api/auth/test/redaktor')
  await page.reload()
  const senaste = page.getByTestId('korningslogg').locator('tbody.korning').first()
  const fore = await senaste.getAttribute('data-korning')
  await page.getByTestId('kor-om-scb').click()
  await expect(senaste).not.toHaveAttribute('data-korning', fore!)
  // Den nya körningen gäller bara SCB.
  await expect(senaste.locator('> tr')).toHaveCount(1)
  await expect(senaste).toContainText('SCB')
  await page.request.post('/api/auth/logga-ut')
})
