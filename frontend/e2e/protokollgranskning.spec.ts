import { expect, test } from '@playwright/test'
import { API_PORT } from '../playwright.config'

// Granskade protokoll (#176): en redaktör eller utgivare markerar ett helt protokoll som granskat, och
// läsaren ser "Granskad av redaktionen ÅÅÅÅ-MM-DD". Granskningen kan tas tillbaka med en motivering.
const api = `http://127.0.0.1:${API_PORT}`
const DATUM = '2026-02-23'

test.beforeAll(async ({ request }) => {
  test.setTimeout(180_000)
  expect((await request.post(`${api}/api/auth/test/redaktor`)).ok()).toBeTruthy()
  expect((await request.post(`${api}/api/insamlingar?kalla=harnosand-protokoll-kf`)).ok()).toBeTruthy()
})

const rad = (page: import('@playwright/test').Page) =>
  page.locator(`[data-testid="sammantrade"][data-datum="${DATUM}"]`)

test('redaktören granskar ett protokoll, läsaren ser datumet och granskningen tas tillbaka', async ({ page }) => {
  // Läsaren ser först att protokollet inte är granskat, och ingen granskningspanel.
  await page.request.post('/api/auth/logga-ut')
  await page.goto('/politik?organ=KF')
  await expect(rad(page).getByTestId('automatiskt-tolkad')).toBeVisible()
  await rad(page).getByRole('rowheader').getByRole('link').click()
  const adress = page.url()
  await expect(page.getByTestId('automatiskt-tolkad')).toHaveText(/Automatiskt tolkad, ej granskad/)
  await expect(page.getByTestId('protokollgranskning')).toHaveCount(0)

  // Redaktören markerar protokollet som granskat.
  await page.request.post('/api/auth/test/redaktor')
  await page.goto(adress)
  const panel = page.getByTestId('protokollgranskning')
  await expect(panel).toContainText('Protokollet har inte granskats.')
  await panel.getByTestId('granska-protokoll').click()
  await expect(panel.getByTestId('granskningsstatus')).toContainText('Granskat av test-redaktor@kommunkollen.test')
  await expect(panel.getByTestId('granskningslogg').locator('li')).toHaveCount(1)
  const markering = page.getByTestId('granskat-protokoll')
  await expect(markering).toHaveText(/^\s*✓\s*Granskad av redaktionen \d{4}-\d{2}-\d{2}\s*$/)
  const datum = (await markering.textContent())?.match(/\d{4}-\d{2}-\d{2}/)?.[0]

  // Läsaren ser datumet men inte vem som granskade, och "Granskad" i listan.
  await page.request.post('/api/auth/logga-ut')
  await page.goto(adress)
  await expect(page.getByTestId('granskat-protokoll')).toHaveText(new RegExp(`Granskad av redaktionen ${datum}`))
  await expect(page.getByTestId('automatiskt-tolkad')).toHaveCount(0)
  await expect(page.getByText('test-redaktor@kommunkollen.test')).toHaveCount(0)
  await page.getByTestId('behandling').first().getByRole('link').first().click()
  await expect(page.getByTestId('granskat-protokoll')).toHaveText(new RegExp(`Granskad av redaktionen ${datum}`))
  await page.goto('/politik?organ=KF')
  await expect(rad(page).getByTestId('granskat-protokoll')).toHaveText(/^\s*✓\s*Granskad\s*$/)
  await expect(rad(page).getByTestId('automatiskt-tolkad')).toHaveCount(0)

  // En utgivare tar tillbaka granskningen med en motivering. Loggen har kvar granskningen.
  await page.request.post('/api/auth/test/utgivare')
  await page.goto(adress)
  await expect(panel.getByTestId('ta-tillbaka-granskning')).toBeDisabled()
  await panel.getByTestId('granskning-motivering').fill('Närvarolistan behöver kontrolleras igen.')
  await panel.getByTestId('ta-tillbaka-granskning').click()
  await expect(panel.getByTestId('granska-protokoll')).toBeEnabled()
  const logg = panel.getByTestId('granskningslogg').locator('li')
  await expect(logg).toHaveCount(1)
  await expect(logg.first()).toHaveAttribute('data-status', 'aterkallad')
  await expect(logg.first()).toContainText('Togs tillbaka av test-utgivare@kommunkollen.test')
  await expect(logg.first()).toContainText('Närvarolistan behöver kontrolleras igen.')
  await expect(page.getByTestId('automatiskt-tolkad')).toBeVisible()

  await page.request.post('/api/auth/logga-ut')
  await page.goto('/politik?organ=KF')
  await expect(rad(page).getByTestId('granskat-protokoll')).toHaveCount(0)
})

test('ett granskat protokoll läst med OCR visas med "läst med OCR"', async ({ page }) => {
  // Inget protokoll i e2e-urvalet är läst med OCR, så svaret för sammanträdet ändras i webbläsaren.
  await page.request.post('/api/auth/logga-ut')
  await page.goto('/politik?organ=KF')
  await rad(page).getByRole('rowheader').getByRole('link').click()
  const id = page.url().match(/sammantraden\/(\d+)/)?.[1]
  await page.route(`**/api/sammantraden/${id}`, async (route) => {
    const svar = await route.fetch()
    await route.fulfill({ response: svar, json: { ...(await svar.json()), ocr: true, granskad: '2026-11-20' } })
  })
  await page.reload()
  await expect(page.getByTestId('granskat-protokoll')).toHaveText(
    /^\s*✓\s*Granskad av redaktionen 2026-11-20 · läst med OCR\s*$/,
  )
  await expect(page.getByTestId('last-med-ocr')).toHaveCount(0)
})

test('en rättelse som inte är publicerad spärrar granskningen', async ({ page }) => {
  await page.request.post('/api/auth/test/redaktor')
  await page.goto('/politik?organ=KF')
  await rad(page).getByRole('rowheader').getByRole('link').click()
  const id = Number(page.url().match(/sammantraden\/(\d+)/)?.[1])
  const s = await (await page.request.get(`/api/sammantraden/${id}`)).json()
  const paragraf = s.behandlingar[0].paragraf
  const r = await page.request.post('/api/rattelser', {
    data: { sammantrade_id: id, objekt: 'behandling', paragraf, falt: 'beslut', nytt: 'Prov.', motivering: 'Prov.',
            felet_i: 'inlasningen' },
  })
  expect(r.ok()).toBeTruthy()
  await page.reload()
  const panel = page.getByTestId('protokollgranskning')
  await expect(panel.getByTestId('granskning-sparr')).toContainText(`§ ${paragraf}, beslutet: utkast`)
  await expect(panel.getByTestId('granska-protokoll')).toBeDisabled()

  // Utkastet tas bort, och då går protokollet att granska igen.
  expect((await page.request.delete(`/api/rattelser/${(await r.json()).id}`)).ok()).toBeTruthy()
  await page.reload()
  await expect(panel.getByTestId('granskning-sparr')).toHaveCount(0)
  await expect(panel.getByTestId('granska-protokoll')).toBeEnabled()
})
