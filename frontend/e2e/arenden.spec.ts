import { expect, test } from '@playwright/test'
import { API_PORT } from '../playwright.config'

const api = `http://127.0.0.1:${API_PORT}`

test.beforeAll(async ({ request }) => {
  test.setTimeout(300_000) // insamlingen tolkar protokollen från KS och KF
  expect((await request.post(`${api}/api/auth/test/redaktor`)).ok()).toBeTruthy()
  for (const kalla of ['harnosand-protokoll-ks', 'harnosand-protokoll-kf']) {
    expect((await request.post(`${api}/api/insamlingar?kalla=${kalla}`)).ok()).toBeTruthy()
  }
})

test('från behandling till ärende till ärendets väg genom organen', async ({ page }) => {
  await page.goto('/politik?organ=KF')
  await page.locator('[data-testid="sammantrade"][data-datum="2026-03-23"]').getByRole('link').click()
  await page.locator('[data-testid="behandling"][data-paragraf="38"]').getByRole('link').click()
  await expect(page).toHaveURL(/\/paragraf\/38$/)

  const arende = page.getByTestId('arende')
  await expect(arende).toContainText('ett ärende med 2 behandlingar')
  await arende.getByTestId('arendelank').click()

  await expect(page).toHaveURL(/\/politik\/arenden\/\d+$/)
  await expect(page.getByRole('heading', { name: 'Borgenstak från 2026', level: 1 })).toBeVisible()
  await expect(page.getByTestId('arende-diarienummer')).toContainText('KS/2026-113')
  const steg = page.getByTestId('vag-behandling')
  await expect(steg).toHaveCount(2)
  await expect(steg.nth(0)).toHaveAttribute('data-organ', 'KS')
  await expect(steg.nth(1)).toHaveAttribute('data-organ', 'KF')
  await expect(steg.nth(0)).toContainText('24 februari 2026')
  const koppling = steg.nth(1).getByTestId('kopplingsstatus')
  await expect(koppling).toHaveAttribute('data-status', 'automatisk')
  await expect(koppling).toContainText('Automatisk koppling via samma diarienummer KS/2026-113')
  await expect(page.getByTestId('slutligt-beslut')).toContainText('Kommunfullmäktige')

  await steg.nth(0).getByRole('link').click()
  await expect(page).toHaveURL(/\/paragraf\/31$/)
  await expect(page.getByRole('heading', { name: 'Borgenstak från 2026', level: 1 })).toBeVisible()
})

test('redaktören bekräftar ett förslag i kön', async ({ page }) => {
  await page.goto('/politik')
  const flikar = page.getByRole('navigation', { name: 'Politik och beslut' })
  await expect(flikar.getByRole('link', { name: 'Kopplingsförslag' })).toHaveCount(0)

  await page.request.post('/api/auth/test/redaktor')
  await page.reload()
  await flikar.getByRole('link', { name: 'Kopplingsförslag' }).click()
  await expect(page).toHaveURL(/\/politik\/kopplingar$/)

  const forslag = page.getByTestId('kopplingsforslag')
  await expect(forslag.first()).toBeVisible()
  const antal = await forslag.count()
  await expect(forslag.first().getByTestId('kopplingsstatus')).toHaveAttribute('data-status', 'forslag')
  await forslag.first().getByTestId('bekrafta').click()

  await expect(forslag).toHaveCount(antal - 1)
  const beslutad = page.getByTestId('beslutade').getByTestId('kopplingsstatus')
  await expect(beslutad).toHaveAttribute('data-status', 'bekraftad')
  await expect(beslutad).toContainText('Bekräftad av redaktör')
  await page.request.post('/api/auth/logga-ut')
})
