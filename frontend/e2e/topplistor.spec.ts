import { expect, test } from '@playwright/test'
import { API_PORT } from '../playwright.config'

// Topplistor per år och mandatperiod (#163).
const api = `http://127.0.0.1:${API_PORT}`
const PARTIER = ['C', 'KD', 'L', 'M', 'MP', 'S', 'SD', 'V']

test.beforeAll(async ({ request }) => {
  test.setTimeout(300_000) // insamlingen tolkar protokollen och läser in valet
  expect((await request.post(`${api}/api/auth/test/redaktor`)).ok()).toBeTruthy()
  for (const kalla of ['harnosand-protokoll-kf', 'valmyndigheten']) {
    expect((await request.post(`${api}/api/insamlingar?kalla=${kalla}`)).ok()).toBeTruthy()
  }
})

test('topplistor i menyn, med alla partier och antal per mandat, och räknade behandlingar', async ({ page, request }) => {
  await page.request.post('/api/auth/logga-ut')
  await page.goto('/politik')
  await page.getByRole('navigation', { name: 'Huvudvyer' }).getByRole('link', { name: 'Topplistor' }).click()
  await expect(page).toHaveURL(/\/politik\/topplistor$/)
  await expect(page.getByRole('heading', { name: 'Topplistor', level: 1 })).toBeVisible()
  await expect(page).toHaveTitle('Topplistor · Politik och beslut · Kommunkollen Härnösand')

  // Det senaste året är förvalt. Åtta listor, och ingen lista över närvaro eller återremisser.
  const t = await (await request.get(`${api}/api/topplistor`)).json()
  await expect(page.getByTestId('topplisteurval')).toHaveValue(String(t.urval.ar))
  await expect(page.getByTestId('topplista')).toHaveCount(8)
  await expect(page.getByRole('heading', { level: 2, name: /närvaro|återremiss/i })).toHaveCount(0)
  // Jämnaste voteringar: skillnaden i procent, minst först.
  const skillnad = await page.locator('[data-lista="jamnaste_voteringar"] [data-testid="skillnad"]').allTextContents()
  expect(skillnad.length).toBeGreaterThan(0)
  for (const s of skillnad) expect(s).toMatch(/^\d+,\d %$/)
  const v = skillnad.map((s) => Number(s.replace(' %', '').replace(',', '.')))
  expect(v).toEqual([...v].sort((a, b) => a - b))

  // Reservationer per parti: alla partier i fullmäktige, med mandat och antal per mandat.
  const lista = page.locator('[data-lista="reservationer_per_parti"]')
  for (const p of PARTIER) await expect(lista.locator(`[data-testid="partirad"][data-parti="${p}"]`)).toBeVisible()
  const sd = t.listor.reservationer_per_parti.rader.find((r: { parti: string }) => r.parti === 'SD')
  const sdRad = lista.locator('[data-testid="partirad"][data-parti="SD"]')
  await expect(sdRad.getByTestId('per-mandat')).toHaveText(
    sd.per_mandat.toLocaleString('sv-SE', { minimumFractionDigits: 2, maximumFractionDigits: 2 }),
  )

  // Ordnat per mandat: högst antal per mandat först.
  await lista.getByTestId('ordna-per-mandat').click()
  const perMandat = await lista
    .locator('[data-testid="partirad"]:not([data-parti=""]) [data-testid="per-mandat"]')
    .allTextContents()
  const tal = perMandat.map((v) => Number(v.replace(',', '.')))
  expect(tal).toEqual([...tal].sort((a, b) => b - a))

  // Raden länkar till behandlingarna som räknats.
  await sdRad.getByTestId('raknade').locator('summary').click()
  await expect(sdRad.getByTestId('raknad')).toHaveCount(sd.antal)
  await sdRad.getByTestId('raknad').first().click()
  await expect(page).toHaveURL(/\/politik\/sammantraden\/\d+\/paragraf\/\d+$/)
  await expect(page.getByTestId('markning').filter({ hasText: /^Reservation/ })).toBeVisible()
})

test('mandatperioden väljs i listan och speglas i URL:en', async ({ page }) => {
  await page.goto('/politik/topplistor')
  await page.getByTestId('topplisteurval').selectOption('mandatperiod-2022')
  await expect(page).toHaveURL(/ar=mandatperiod&period=2022/)
  await expect(page.getByTestId('underlag')).toContainText('15 okt 2022–14 okt 2026')
  await page.reload()
  await expect(page.getByTestId('topplisteurval')).toHaveValue('mandatperiod-2022')
  await expect(page.locator('[data-lista="motioner_per_parti"]')).toContainText('mandatperioden 2022–2026')
})

test('topplistorna på mobil och i mörkt läge', async ({ page }) => {
  await page.setViewportSize({ width: 375, height: 812 })
  await page.goto('/politik/topplistor')
  await expect(page.getByTestId('topplista').first()).toBeVisible()
  // Sidan blir inte bredare än skärmen. Breda tabeller rullar i sitt kort.
  expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBeLessThanOrEqual(375)

  const yta = () => page.getByTestId('topplista').first().evaluate((e) => getComputedStyle(e).backgroundColor)
  const ljus = await yta()
  await page.emulateMedia({ colorScheme: 'dark' })
  await expect.poll(yta).not.toBe(ljus)
})
