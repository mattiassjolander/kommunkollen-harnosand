import { expect, test } from '@playwright/test'
import { API_PORT } from '../playwright.config'

const api = `http://127.0.0.1:${API_PORT}`

test.beforeAll(async ({ request }) => {
  test.setTimeout(300_000) // insamlingen tolkar fullmäktiges protokoll
  // Förbered data: fullmäktiges protokoll och de fem organens sammanträdesplaner (#68).
  expect((await request.post(`${api}/api/auth/test/redaktor`)).ok()).toBeTruthy()
  for (const kalla of ['harnosand-protokoll-kf', 'harnosand-sammantradesplaner']) {
    expect((await request.post(`${api}/api/insamlingar?kalla=${kalla}`)).ok()).toBeTruthy()
  }
})

test('redaktören ser sammanträdesplanerna med inställda möten, ändrade tider och protokoll (#68)', async ({ page }) => {
  await page.goto('/politik')
  const flikar = page.getByRole('navigation', { name: 'Politik och beslut' })
  // Planerna och skillnaderna mot besluten visas inte publikt.
  await expect(flikar.getByRole('link', { name: 'Planer', exact: true })).toHaveCount(0)

  await page.request.post('/api/auth/test/redaktor')
  await page.reload()
  await flikar.getByRole('link', { name: 'Planer', exact: true }).click()
  await expect(page).toHaveURL(/\/politik\/sammantradesplaner$/)

  const planer = page.getByTestId('sammantradesplan')
  await expect(planer).toHaveCount(6) // KF, KS 2026 och 2027, och de tre nämnderna

  await page.getByTestId('organfilter').selectOption('KF')
  await expect(page).toHaveURL(/organ=KF/)
  const kf = page.locator('[data-testid="sammantradesplan"][data-organ="KF"][data-ar="2026"]')
  await expect(planer).toHaveCount(1)
  await expect(kf.getByRole('heading', { name: 'Kommunfullmäktige 2026' })).toBeVisible()
  await expect(kf.getByTestId('planerat-sammantrade')).toHaveCount(10)

  const installt = kf.locator('[data-nyckel="2026-10-15"]')
  await expect(installt).toHaveAttribute('data-status', 'installt')
  await expect(installt).toContainText('Inställt')
  await expect(kf.locator('[data-nyckel="2026-10-26"]')).toContainText('kl. 11.00')

  // Hållna sammanträden har sitt protokoll kopplat.
  await kf.locator('[data-nyckel="2026-03-23"]').getByRole('link', { name: 'Protokoll' }).click()
  await expect(page).toHaveURL(/\/politik\/sammantraden\/\d+$/)
  await expect(page.getByRole('heading', { level: 1 })).toContainText('Kommunfullmäktige')

  await page.goto('/politik/sammantradesplaner?organ=SOC')
  const soc = page.locator('[data-testid="sammantradesplan"][data-organ="SOC"]')
  await expect(soc.locator('[data-nyckel="2026-06"]')).toContainText('juni 2026')
  await expect(soc.locator('[data-nyckel="2026-06"]')).toHaveAttribute('data-status', 'installt')
  await expect(soc.getByRole('link', { name: 'Socialnämnden på harnosand.se' })).toHaveAttribute(
    'href',
    /socialnamnden\.html$/,
  )
})
