import { expect, test } from '@playwright/test'
import { API_PORT } from '../playwright.config'

// Styrande dokument (#63): listan och dokumentsidan, från den inspelade sidan Kommunens styrande dokument med en fil
// per rubrik (STYRANDE_URVAL=1). Dagens datum är låst till 2026-11-20.

const api = `http://127.0.0.1:${API_PORT}`

test.beforeAll(async ({ request }) => {
  test.setTimeout(120_000)
  expect((await request.post(`${api}/api/auth/test/redaktor`)).ok()).toBeTruthy()
  expect((await request.post(`${api}/api/insamlingar?kalla=harnosand-styrande-dokument`)).ok()).toBeTruthy()
})

test('listan visar gällande dokument och kan filtreras på kategori, fastställt av och giltighet', async ({ page }) => {
  await page.goto('/politik')
  const nav = page.getByRole('navigation', { name: 'Huvudvyer' })
  await nav.getByRole('link', { name: 'Styrande dokument' }).click()
  await expect(page).toHaveURL(/\/politik\/styrande-dokument$/)
  await expect(page.getByRole('heading', { name: 'Styrande dokument', level: 1 })).toBeVisible()

  const rader = page.getByTestId('styrdokument')
  // Gällande är förvalt: 7 av de 10 inspelade dokumenten.
  await expect(rader).toHaveCount(7)
  await expect(page.getByTestId('kallrad')).toContainText('harnosand.se, Kommunens styrande dokument')

  await page.getByTestId('giltighet').selectOption('utganget')
  await expect(rader).toHaveCount(3)
  const bostad = rader.filter({ hasText: 'Bostadsförsörjningsprogram med riktlinjer 2017-2022' })
  await expect(bostad.getByTestId('giltighetsmarkering')).toHaveText('Utgånget 31 dec 2022')

  await page.getByTestId('giltighet').selectOption('alla')
  await expect(rader).toHaveCount(10)
  await page.getByTestId('kategori').selectOption('Delegationer')
  await expect(rader).toHaveCount(1)
  await expect(rader).toContainText('Delegationsordning för samhällsnämnden')
  await expect(rader).toContainText('Samhällsnämnden, 26 mars 2026')

  await page.getByTestId('kategori').selectOption('')
  await page.getByTestId('faststallt').selectOption({ label: 'Kommunfullmäktige' })
  await expect(rader).toHaveCount(5)
  // Urvalet speglas i adressen.
  await expect(page).toHaveURL(/giltighet=alla/)
  await expect(page).toHaveURL(/faststallt=KF/)
})

test('dokumentsidan visar dokumentinformationen, giltigheten med källa och versionen', async ({ page }) => {
  await page.goto('/politik/styrande-dokument?giltighet=alla&kategori=Delegationer')
  await page.getByTestId('styrdokument').getByRole('link').click()
  await expect(page).toHaveURL(/\/politik\/styrande-dokument\/\d+$/)
  await expect(page.getByRole('heading', { name: 'Delegationsordning för samhällsnämnden', level: 1 })).toBeVisible()
  await expect(page).toHaveTitle('Delegationsordning för samhällsnämnden · Styrande dokument · Politik och beslut · Kommunkollen Härnösand')

  await expect(page.getByTestId('meta')).toContainText('Delegationer')
  await expect(page.getByTestId('pdf-kommunen')).toHaveAttribute('href', /harnosand\.se\/download\/18\.4b6c551c1679dec5d0a4a691\//)
  await expect(page.getByTestId('giltighet')).toContainText('Giltig t o m 2027-03-26 enligt dokumentinformationen.')

  const info = page.getByTestId('dokumentinformation')
  await expect(info.getByTestId('falt-faststalld_av')).toHaveText('Samhällsnämnden')
  await expect(info.getByTestId('falt-diarienummer')).toHaveText('SAM 2025-000041')
  await expect(info.getByTestId('falt-dokumenttyp')).toHaveText('Styrdokument')
  await expect(info.getByTestId('falt-dokumentinformation')).toHaveText('Uppgift saknas')

  await expect(page.getByTestId('inget-beslut')).toBeVisible()
  const versioner = page.getByTestId('version')
  await expect(versioner).toHaveCount(1)
  await expect(versioner).toContainText('Gällande')
  const kopia = await page.getByTestId('pdf-kopia').getAttribute('href')
  expect(kopia).toMatch(/^\/api\/styrande-dokument\/\d+\/versioner\/1$/)
  const pdf = await page.request.get(`${api}${kopia}`)
  expect(pdf.headers()['content-type']).toBe('application/pdf')

  // Inga värderande ord.
  await expect(page.locator('main')).not.toContainText(/\bfel\b|brist|slarv/i)
})

test('ett dokument utan ruta visar det och anger giltigheten ur titeln', async ({ page }) => {
  await page.goto('/politik/styrande-dokument?giltighet=alla')
  await page.getByRole('link', { name: 'Bostadsförsörjningsprogram med riktlinjer 2017-2022' }).click()
  await expect(page.getByTestId('ingen-ruta')).toBeVisible()
  await expect(page.getByTestId('giltighet')).toContainText(
    'Perioden i titeln är 2017–2022, giltig t o m 2022-12-31. Dokumentet ligger kvar på kommunens sida.',
  )
  await expect(page.getByTestId('giltighet')).toContainText('Giltigheten är läst enligt perioden i titeln.')
})

test('sidorna går att söka fram och leder till dokumentsidan', async ({ page }) => {
  await page.goto('/sok?q=delegationsordning&typ=styrande_dokument')
  const traff = page.locator('[data-testid="traff"][data-typ="styrande_dokument"]').first()
  await expect(traff).toContainText('Styrande dokument')
  await traff.getByTestId('traff-lank').click()
  await expect(page).toHaveURL(/\/politik\/styrande-dokument\/\d+$/)
})
