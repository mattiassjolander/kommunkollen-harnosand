import { expect, test } from '@playwright/test'
import { API_PORT } from '../playwright.config'

test.beforeAll(async ({ request }) => {
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
    await expect(indikator).toContainText('2 av 2 kontrollerade utan fel') // Kolada och SCB
  }
})

test('vyn Datakällor visar status per källa och körningsloggen', async ({ page }) => {
  await page.goto('/ekonomi')
  await page.getByRole('navigation', { name: 'Huvudvyer' }).getByRole('link', { name: 'Datakällor' }).click()
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
