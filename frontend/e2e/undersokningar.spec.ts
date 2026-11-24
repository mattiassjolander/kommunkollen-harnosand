import { expect, test } from '@playwright/test'
import { API_PORT } from '../playwright.config'

// Undersökningar (#67): medborgarundersökningen, Insikt och anmälda brott från de inspelade Kolada-svaren.

test.beforeAll(async ({ request }) => {
  test.setTimeout(180_000) // insamlingen tolkar ett femtiotal protokoll
  const api = `http://127.0.0.1:${API_PORT}`
  expect((await request.post(`${api}/api/auth/test/redaktor`)).ok()).toBeTruthy()
  expect((await request.post(`${api}/api/insamlingar`)).ok()).toBeTruthy()
})

test('sidan är öppen och visar svarsfrekvensen överst med källa och riket', async ({ page }) => {
  await page.goto('/')
  await page.getByRole('link', { name: 'Undersökningar' }).click()
  await expect(page.getByRole('heading', { name: 'Undersökningar', level: 1 })).toBeVisible()
  await expect(page.getByTestId('anvandare').getByRole('button', { name: 'Logga in' })).toBeVisible()

  const avsnitt = page.getByTestId('avsnitt')
  await expect(avsnitt).toHaveCount(3)
  const mu = page.locator('[data-avsnitt="medborgarundersokningen"]')
  await expect(mu.getByTestId('avsnittskalla')).toHaveText('Källa: SCB/Kolada')

  // Svarsfrekvensen och antalet svar först.
  const forsta = mu.getByTestId('nyckeltal').first()
  await expect(forsta).toHaveAttribute('data-matt', 'kolada:N00529')
  await expect(forsta.getByRole('heading', { name: 'Svarsfrekvens, andel (%)' })).toBeVisible()
  await expect(mu.getByTestId('nyckeltal').nth(1)).toHaveAttribute('data-matt', 'kolada:N00528')
  await expect(forsta.getByTestId('kallrad')).toContainText('SCB/Kolada (N00529)')
  await expect(forsta.getByTestId('kallrad')).toContainText('Avser 2021–2025')
  // Urvalet: 26 nyckeltal.
  await expect(mu.locator('.grupp:not([data-testid="alla-fragor"]) [data-testid="nyckeltal"]')).toHaveCount(26)

  // Härnösand och riket i tabellen.
  await page.getByTestId('vy').getByRole('button', { name: 'Tabell' }).click()
  await expect(page).toHaveURL(/vy=tabell/)
  const rad2021 = forsta.getByRole('row').filter({ hasText: '2021' })
  await expect(rad2021).toContainText('37,4')
  await expect(rad2021.getByTestId('riketcell')).toHaveText('37,6')
})

test('Insikt visar den gamla och den nya definitionen som separata serier med metodbytet', async ({ page }) => {
  await page.goto('/undersokningar?vy=tabell')
  const insikt = page.locator('[data-avsnitt="insikt"]')
  await expect(insikt.getByTestId('avsnittskalla')).toHaveText('Källa: SKR/Kolada')

  const metodbyte = insikt.getByTestId('metodbyte')
  await expect(metodbyte).toContainText('Metodbyte 2024')
  await expect(metodbyte.getByTestId('metodbyte-text')).toContainText('slås inte ihop')
  await expect(metodbyte.getByRole('columnheader', { name: 'Gammal definition (till 2024)', exact: true })).toBeVisible()
  await expect(metodbyte.getByRole('columnheader', { name: 'Ny definition (från 2024)', exact: true })).toBeVisible()
  // 2025 finns bara i den nya definitionen. Den gamla har ingen uppgift det året.
  const rad2025 = metodbyte.getByRole('row').filter({ hasText: '2025' })
  await expect(rad2025.getByRole('cell').nth(1)).toHaveText('Uppgift saknas')
  // Kolumnerna: år, gammal definition, gammal definition för riket och ny definition (Kolada har inget riket för den).
  await expect(rad2025.getByRole('cell').nth(3)).toHaveText('86,1')

  // Diagrammet har en linje per definition.
  await page.getByTestId('vy').getByRole('button', { name: 'Diagram' }).click()
  await expect(metodbyte.getByLabel('Teckenförklaring')).toContainText('Gammal definition (till 2024)')
  await expect(metodbyte.getByLabel('Teckenförklaring')).toContainText('Ny definition (från 2024)')

  // Saknade värden visas som "Uppgift saknas", aldrig som noll.
  await page.getByTestId('vy').getByRole('button', { name: 'Tabell' }).click()
  const brandskydd = insikt.locator('[data-matt="kolada:U07446"]')
  await expect(brandskydd.getByRole('row').filter({ hasText: '2025' }).getByRole('cell').nth(1)).toHaveText(
    'Uppgift saknas',
  )
})

test('anmälda brott visas med texten om vad statistiken mäter', async ({ page }) => {
  await page.goto('/undersokningar#anmalda-brott')
  const brott = page.locator('[data-avsnitt="anmalda-brott"]')
  await expect(brott.getByTestId('avsnittskalla')).toHaveText('Källa: Brå/Kolada')
  await expect(brott.getByTestId('om-matningen')).toContainText('inte hur många brott som faktiskt begås')
  await expect(brott.getByTestId('nyckeltal')).toHaveCount(9)
  await expect(brott.getByTestId('nyckeltal').first()).toHaveAttribute('data-matt', 'kolada:N07540')
})

test('alla frågor i medborgarundersökningen nås i analysverktyget', async ({ page }) => {
  await page.goto('/undersokningar')
  const alla = page.getByTestId('alla-fragor')
  const val = alla.getByTestId('valj-fraga')
  await expect(val.locator('option')).toHaveCount(115) // 114 nyckeltal och "Välj nyckeltal"
  await val.selectOption('N00544')
  await expect(page).toHaveURL(/fraga=N00544/)
  const kort = alla.locator('[data-matt="kolada:N00544"]')
  await expect(kort.getByRole('heading')).toContainText('tyst och lugnt')
  await expect(kort.getByTestId('kallrad')).toContainText('SCB/Kolada (N00544)')
})
