import { expect, test } from '@playwright/test'
import { API_PORT } from '../playwright.config'

const api = `http://127.0.0.1:${API_PORT}`

test.beforeAll(async ({ request }) => {
  test.setTimeout(180_000) // insamlingen tolkar ett femtiotal protokoll
  expect((await request.post(`${api}/api/auth/test/redaktor`)).ok()).toBeTruthy()
  expect((await request.post(`${api}/api/insamlingar?kalla=harnosand-protokoll-kf`)).ok()).toBeTruthy()
})

test('votering per parti och per ledamot, med yrkanden och reservationer', async ({ page }) => {
  await page.goto('/politik?organ=KF')
  await page.locator('[data-testid="sammantrade"][data-datum="2026-02-23"]').getByRole('rowheader').getByRole('link').click()
  const rad = page.locator('[data-testid="behandling"][data-paragraf="5"]')
  await expect(rad.locator('[data-markning="votering"]')).toHaveText('Votering 37–6')
  await expect(rad.locator('[data-markning="reservation"]')).toBeVisible()
  await rad.getByRole('link').first().click()
  await expect(page).toHaveURL(/\/paragraf\/5$/)

  await expect(page.getByTestId('yrkande').first()).toBeVisible()
  const v = page.getByTestId('votering')
  await expect(v).toHaveCount(1)
  await expect(v.getByTestId('ja-forslag')).toHaveText('kommunstyrelsens förslag')
  await expect(v.getByTestId('nej-forslag')).toHaveText('Göran Sjögrens (SD) förslag')
  await expect(v.getByTestId('utfall')).toContainText('37 ja, 6 nej')
  await expect(v.getByTestId('avvikelse')).toHaveCount(0)
  await expect(v.getByTestId('vinnare')).toContainText('kommunstyrelsens förslag')

  // Per parti: förkortning och siffror, aldrig bara färg.
  const sd = v.locator('[data-testid="partirad"][data-parti="SD"]')
  await expect(sd.getByTestId('parti')).toHaveText('SD')
  await expect(sd.getByTestId('nej')).toHaveText('6')
  await expect(sd.getByTestId('ja')).toHaveText('0')

  // Per ledamot: listan som den står i protokollet.
  await v.getByTestId('per-ledamot').locator('summary').click()
  await expect(v.getByTestId('rost')).toHaveCount(43)
  const molin = v.getByTestId('rost').filter({ hasText: 'Lennart Molin' })
  await expect(molin).toContainText('ersättare för Nina Skyttberg (S)')
  await expect(molin).toHaveAttribute('data-rost', 'ja')
  await expect(v.getByTestId('rost').filter({ hasText: 'Göran Virén Sjögren' })).toHaveAttribute('data-rost', 'nej')

  await expect(page.getByTestId('reservation')).toHaveCount(2)
  await expect(page.getByTestId('reservation').first().getByTestId('parti')).toHaveText('SD')

  // Från rösten till ledamotens sida och tillbaka till behandlingen.
  await molin.getByRole('link', { name: 'Lennart Molin' }).click()
  await expect(page).toHaveURL(/\/politik\/ledamoter\/\d+$/)
  const rost = page.locator('[data-testid="ledamotens-rost"][data-datum="2026-02-23"][data-paragraf="5"]')
  await expect(rost).toHaveAttribute('data-rost', 'ja')
  await expect(rost).toContainText('ersättare för Nina Skyttberg')
  await rost.getByRole('link').click()
  await expect(page).toHaveURL(/\/paragraf\/5$/)
  await expect(page.getByTestId('votering')).toBeVisible()
})

test('avstår enligt voteringslistan, med ankare till voteringen', async ({ page }) => {
  await page.goto('/politik?organ=KF')
  await page.locator('[data-testid="sammantrade"][data-datum="2026-03-23"]').getByRole('rowheader').getByRole('link').click()
  await page.locator('[data-testid="behandling"][data-paragraf="39"]').getByRole('link').click()
  const v = page.getByTestId('votering')
  await expect(v).toHaveCount(1)
  await expect(v).toHaveAttribute('id', 'votering-1')
  await expect(v.getByTestId('utfall')).toContainText('28 ja, 6 nej, 8 avstår')
  await v.getByTestId('per-ledamot').locator('summary').click()
  await expect(v.getByTestId('rost').filter({ hasText: 'Eva-Clara Viklund' })).toContainText('Avstår')
})
