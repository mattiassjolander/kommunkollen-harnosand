import { expect, test } from '@playwright/test'
import { API_PORT } from '../playwright.config'

test.beforeAll(async ({ request }) => {
  // Förbered data: logga in som redaktör och kör en insamling mot de inspelade Kolada-svaren.
  const api = `http://127.0.0.1:${API_PORT}`
  expect((await request.post(`${api}/api/auth/test/redaktor`)).ok()).toBeTruthy()
  expect((await request.post(`${api}/api/insamlingar`)).ok()).toBeTruthy()
})

test('ekonomivyn är öppen och visar årets resultat som tidsserie med källrad', async ({ page }) => {
  await page.goto('/ekonomi')

  // Ingen inloggning krävs för att läsa.
  await expect(page.getByTestId('anvandare').getByRole('button', { name: 'Logga in' })).toBeVisible()

  const kort = page.locator('[data-matt="kolada:N03007"]')
  await expect(kort.getByRole('heading', { name: 'Årets resultat kommun, kr/inv' })).toBeVisible()

  // Standardvisning från 2022: 2022–2025 i inspelningen.
  await expect(kort.getByTestId('stapel')).toHaveCount(4)

  const kallrad = kort.getByTestId('kallrad')
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
})

test('redaktör kan logga in och ut och stannar på sidan', async ({ page }) => {
  await page.goto('/ekonomi')
  await page.getByTestId('anvandare').getByRole('button', { name: 'Logga in' }).click()

  // Läsare finns inte som val när läsning är öppen.
  await expect(page.getByRole('button', { name: 'Logga in som läsare (test)' })).toHaveCount(0)
  await page.getByRole('button', { name: 'Logga in som redaktör (test)' }).click()
  await expect(page.getByTestId('anvandare')).toContainText('Test (redaktor)')
  await expect(page.getByTestId('nyckeltal').first()).toBeVisible()

  await page.getByRole('button', { name: 'Logga ut' }).click()
  await expect(page.getByTestId('anvandare').getByRole('button', { name: 'Logga in' })).toBeVisible()
  await expect(page.getByTestId('nyckeltal').first()).toBeVisible()
})

test('man kan avbryta inloggningen och fortsätta läsa', async ({ page }) => {
  await page.goto('/ekonomi')
  await page.getByTestId('anvandare').getByRole('button', { name: 'Logga in' }).click()
  await page.getByRole('button', { name: 'Fortsätt utan att logga in' }).click()
  await expect(page.getByTestId('nyckeltal').first()).toBeVisible()
})

test('ej behörigt Google-konto får ett tydligt meddelande', async ({ page }) => {
  await page.goto('/?fel=ej-behorig')
  await expect(page.getByTestId('inloggningsfel')).toContainText('har inte åtkomst')
})

test('ett nyckeltal kan växlas mellan diagram och tabell', async ({ page }) => {
  await page.goto('/ekonomi')
  const kort = page.locator('[data-matt="scb:BalansKnN:065"]')
  await expect(kort.getByRole('heading', { name: 'Likvida medel' })).toBeVisible()
  await expect(kort.getByTestId('stapel').first()).toBeVisible()

  await kort.getByRole('button', { name: 'Tabell' }).click()
  await expect(kort.getByTestId('stapel')).toHaveCount(0)
  const tabell = kort.getByRole('table')
  await expect(tabell.getByRole('columnheader', { name: 'mnkr' })).toBeVisible() // tkr från SCB visas i mnkr
  await expect(tabell.getByRole('row')).toHaveCount(1 + 4) // rubrik + 2022–2025

  const kallrad = kort.getByTestId('kallrad')
  await expect(kallrad).toContainText('SCB')
  await expect(kallrad).toContainText('BalansKnN, post 065')
  await expect(kallrad).toContainText('Löpande priser')
})

test('visningen startar 2022 men kan börja tidigare, och valet speglas i URL:en', async ({ page }) => {
  await page.goto('/ekonomi')
  const kort = page.locator('[data-matt="scb:BalansKnN:065"]')
  await expect(kort.getByTestId('stapel')).toHaveCount(4)

  await page.getByTestId('fran-ar').selectOption('1998')
  await expect(page).toHaveURL(/fran=1998/)
  await expect(kort.getByTestId('stapel')).toHaveCount(2025 - 1998 + 1)

  await page.reload()
  await expect(page.getByTestId('fran-ar')).toHaveValue('1998')
})
