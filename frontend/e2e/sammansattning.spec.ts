import { expect, test } from '@playwright/test'
import { API_PORT } from '../playwright.config'

// Sammansättning (#65): Valmyndighetens filer är inspelade med bara Härnösands rader.

test.beforeAll(async ({ request }) => {
  test.setTimeout(180_000)
  const api = `http://127.0.0.1:${API_PORT}`
  expect((await request.post(`${api}/api/auth/test/redaktor`)).ok()).toBeTruthy()
  expect((await request.post(`${api}/api/insamlingar`)).ok()).toBeTruthy()
})

test('kön och ålder för kandidater, valda och tjänstgörande, med filter i URL:en', async ({ page }) => {
  await page.request.post('/api/auth/logga-ut')
  await page.goto('/politik')
  await page.getByRole('navigation', { name: 'Politik och beslut' }).getByRole('link', { name: 'Sammansättning' }).click()
  await expect(page).toHaveURL(/\/politik\/sammansattning$/)
  await expect(page.getByTestId('konstext')).toContainText('Kön enligt folkbokföringen (Valmyndigheten)')

  // Valda 2026: 43 ledamöter, och de röstberättigade som referens.
  const valda = page.getByTestId('led-valda')
  await expect(valda.locator('[data-grupp="totalt"]').first()).toContainText('43')
  await expect(valda.locator('[data-grupp="NP"]').first()).toBeVisible()
  await expect(valda.getByTestId('referensrad')).toContainText('Röstberättigade 2026')
  await expect(valda.getByTestId('kallrad')).toContainText('Valmyndigheten')
  await expect(valda.getByTestId('csv')).toHaveAttribute('download', /\.csv$/)
  await valda.getByText('Visa som tabell').click()
  await expect(valda.getByTestId('sammansattningstabell').locator('tr[data-grupp="totalt"]')).toContainText('22')

  await expect(page.getByTestId('led-kandidater').locator('[data-grupp="totalt"]').first()).toContainText('182')
  await expect(page.getByTestId('led-topp')).toBeVisible()
  // Inga uppgifter per person för läsaren.
  await expect(page.getByTestId('sammansattning-redaktion')).toHaveCount(0)

  // 2022: kandidaternas uppgifter är gallrade och "uppgift saknas" är en egen grupp.
  await page.getByTestId('filter-period').selectOption('2022')
  await expect(page).toHaveURL(/period=2022/)
  await expect(page.getByTestId('led-kandidater').getByTestId('kon-saknas').first()).toBeVisible()
  await expect(page.getByTestId('led-topp')).toHaveCount(0)
  await expect(page.getByTestId('led-tjanstgorande')).toBeVisible()

  // En nämnd har inga egna kandidater.
  await page.getByTestId('filter-organ').selectOption('SOC')
  await expect(page).toHaveURL(/organ=SOC/)
  await page.reload()
  await expect(page.getByTestId('inga-kandidater')).toBeVisible()
  await expect(page.getByTestId('filter-organ')).toHaveValue('SOC')
})

test('redaktionen bekräftar kopplingar och anger kön med källa som en annan utgivare publicerar', async ({ page }) => {
  await page.request.post('/api/auth/logga-ut')
  await page.request.post('/api/auth/test/redaktor')
  await page.goto('/politik/sammansattning')
  const redaktion = page.getByTestId('sammansattning-redaktion')
  await expect(redaktion).toBeVisible()
  await expect(redaktion).toContainText('Att gissa kön utifrån namn eller bild är inte tillåtet')

  // Ett kopplingsförslag bekräftas.
  const forslag = redaktion.getByTestId('valkoppling')
  await expect(forslag.first()).toBeVisible()
  const id = await forslag.first().getAttribute('data-id')
  await forslag.first().getByTestId('bekrafta').click()
  await expect(redaktion.locator(`[data-testid="valkoppling"][data-id="${id}"]`)).toHaveCount(0)

  // Kön och födelseår med källa för en person utan uppgift.
  const person = redaktion.getByTestId('uppgift-person')
  const namn = (await person.locator('option').nth(1).textContent())!.trim()
  await person.selectOption({ index: 1 })
  await redaktion.getByTestId('uppgift-kon').selectOption('K')
  await redaktion.getByTestId('uppgift-fodelsear').fill('1970')
  await redaktion.getByTestId('uppgift-kalla').fill('Partiets kandidatlista 2026, sida 2')
  await redaktion.getByTestId('spara-uppgift').click()
  const uppgift = redaktion.getByTestId('personuppgift').filter({ hasText: namn })
  await expect(uppgift).toHaveAttribute('data-status', 'utkast')
  // Redaktören kan inte granska sin egen uppgift.
  await expect(uppgift.getByTestId('granska')).toHaveCount(0)

  await page.request.post('/api/auth/logga-ut')
  await page.request.post('/api/auth/test/utgivare')
  await page.reload()
  await uppgift.getByTestId('granska').click()
  await expect(uppgift).toHaveAttribute('data-status', 'granskad')
  await uppgift.getByTestId('publicera').click()
  await expect(uppgift).toHaveCount(0)
})
