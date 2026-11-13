import { expect, test } from '@playwright/test'
import { API_PORT } from '../playwright.config'

test.beforeAll(async ({ request }) => {
  // Förbered data: logga in som redaktör och kör en insamling mot de inspelade Kolada-svaren.
  const api = `http://127.0.0.1:${API_PORT}`
  expect((await request.post(`${api}/api/auth/test/redaktor`)).ok()).toBeTruthy()
  expect((await request.post(`${api}/api/insamlingar`)).ok()).toBeTruthy()
})

test('oinloggad ser inloggningssidan i stället för innehållet', async ({ page }) => {
  await page.goto('/ekonomi')
  await expect(page.getByRole('button', { name: 'Logga in som läsare (test)' })).toBeVisible()
  await expect(page.getByTestId('nyckeltal')).toHaveCount(0)
})

test('ej behörigt Google-konto får ett tydligt meddelande', async ({ page }) => {
  await page.goto('/?fel=ej-behorig')
  await expect(page.getByTestId('inloggningsfel')).toContainText('har inte åtkomst')
})

test('ekonomivyn visar årets resultat som tidsserie med källrad', async ({ page }) => {
  await page.goto('/ekonomi')
  await page.getByRole('button', { name: 'Logga in som läsare (test)' }).click()
  await expect(page.getByTestId('anvandare')).toContainText('Test (lasare)')

  const kort = page.getByTestId('nyckeltal')
  await expect(kort.getByRole('heading', { name: 'Årets resultat kommun, kr/inv' })).toBeVisible()

  // Standardvisning från 2022: 2022–2025 i inspelningen.
  await expect(kort.getByTestId('stapel')).toHaveCount(4)

  const kallrad = page.getByTestId('kallrad')
  await expect(kallrad).toContainText('Kolada')
  await expect(kallrad).toContainText('N03007')
  await expect(kallrad).toContainText('Avser 2022–2025')
  await expect(kallrad).toContainText('Publicerad 28 aug 2026')

  // Tooltip vid hover visar år, värde med enhet och källa.
  const yta = kort.locator('rect.traffyta').last()
  await yta.hover()
  const tips = page.getByRole('tooltip')
  await expect(tips).toContainText('2025')
  await expect(tips).toContainText('972 kr/inv')
  await expect(tips).toContainText('Kolada')

  // Utloggning visar inloggningssidan igen.
  await page.getByRole('button', { name: 'Logga ut' }).click()
  await expect(page.getByRole('button', { name: 'Logga in som läsare (test)' })).toBeVisible()
})
