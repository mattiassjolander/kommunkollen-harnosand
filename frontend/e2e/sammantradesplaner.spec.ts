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
  const flikar = page.getByRole('navigation', { name: 'Huvudvyer' })
  // Planerna och skillnaderna mot besluten visas inte publikt.
  await expect(flikar.getByRole('link', { name: 'Redaktion' })).toHaveCount(0)

  await page.request.post('/api/auth/test/redaktor')
  await page.reload()
  await flikar.getByRole('link', { name: 'Redaktion' }).click()
  await flikar.getByRole('link', { name: 'Sammanträdesplaner', exact: true }).click()
  await expect(page).toHaveURL(/\/redaktion\/sammantradesplaner$/)

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

  // Källan per sammanträde (#99).
  await expect(kf.getByTestId('kalla').first()).toHaveText('Webbsidan')
  // Hållna sammanträden har sitt protokoll kopplat.
  await kf.locator('[data-nyckel="2026-03-23"]').getByRole('link', { name: 'Protokoll' }).click()
  await expect(page).toHaveURL(/\/politik\/sammantraden\/\d+$/)
  await expect(page.getByRole('heading', { level: 1 })).toContainText('Kommunfullmäktige')

  await page.goto('/redaktion/sammantradesplaner?organ=SOC')
  const soc = page.locator('[data-testid="sammantradesplan"][data-organ="SOC"]')
  await expect(soc.locator('[data-nyckel="2026-06"]')).toContainText('juni 2026')
  await expect(soc.locator('[data-nyckel="2026-06"]')).toHaveAttribute('data-status', 'installt')
  await expect(soc.getByRole('link', { name: 'Socialnämnden på harnosand.se' })).toHaveAttribute(
    'href',
    /socialnamnden\.html$/,
  )
})

test('diarienummer som protokollet saknar visas ur kallelsen med länk till sidan (#109)', async ({ page }) => {
  // Kompletteringen ur kallelsen testas mot riktiga kallelser i backend (test_diarienummer_ur_kallelsen.py).
  // Inspelningarna här har inte de kallelserna, så svaret får källan för den första behandlingen.
  const kalla = {
    titel: 'Handlingar kommunfullmäktige 2026-03-23',
    typ: 'handlingar',
    url: 'https://www.harnosand.se/handlingar.pdf#page=6',
    sida: 6,
  }
  await page.request.post('/api/auth/test/lasare')
  const sammantraden = await (await page.request.get('/api/sammantraden?organ=KF')).json()
  const s = sammantraden.find((x: { datum: string }) => x.datum === '2026-03-23')
  expect(s).toBeTruthy()
  await page.route(/\/api\/sammantraden\/\d+$/, async (route) => {
    const svar = await route.fetch()
    const data = await svar.json()
    const b = data.behandlingar[0]
    b.diarienummer = ['KS/2026-533']
    b.diarienummer_kallelse = kalla
    await route.fulfill({ response: svar, json: data })
  })

  await page.goto(`/politik/sammantraden/${s.id}`)
  const rad = page.locator('[data-testid="behandling"]').first()
  await expect(rad.locator('.dnr')).toHaveText('KS/2026-533')
  await expect(rad.getByTestId('dnr-ur-kallelsen')).toContainText('ur kallelsen')
  await expect(page.locator('[data-testid="behandling"]').nth(1).getByTestId('dnr-ur-kallelsen')).toHaveCount(0)

  await rad.getByTestId('dnr-ur-kallelsen').getByText('ur kallelsen').click()
  const lank = rad.getByTestId('kallelselank')
  await expect(lank).toHaveText('Handlingar kommunfullmäktige 2026-03-23, sidan 6')
  await expect(lank).toHaveAttribute('href', kalla.url)
})
