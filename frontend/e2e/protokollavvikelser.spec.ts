import { expect, test } from '@playwright/test'
import { API_PORT } from '../playwright.config'

const api = `http://127.0.0.1:${API_PORT}`

test.beforeAll(async ({ request }) => {
  test.setTimeout(180_000)
  expect((await request.post(`${api}/api/auth/test/redaktor`)).ok()).toBeTruthy()
  expect((await request.post(`${api}/api/insamlingar?kalla=harnosand-protokoll-kf`)).ok()).toBeTruthy()
})

// Söm 2 (#47): redaktören markerar en avvikelse som anmäld och utgivaren ser statusen. Att anmäla är redaktionens
// verktyg och visas inte för läsare (#160).
test('redaktören anmäler en protokollavvikelse och utgivaren ser statusen', async ({ page }) => {
  await page.request.post('/api/auth/test/redaktor')
  await page.goto('/politik/avvikelser?organ=KF&fran=2026&till=2026')
  await page.getByTestId('att-anmala').click()
  await expect(page).toHaveURL(/\/redaktion\/att-anmala$/)
  const nav = page.getByRole('navigation', { name: 'Huvudvyer' })
  await expect(nav.getByRole('link', { name: 'Att anmäla' })).toHaveAttribute('aria-current', 'page')
  await expect(page.getByTestId('brodsmula')).toHaveText('Redaktion ›')
  await page.getByTestId('filter-organ').selectOption('KF')
  await page.getByTestId('filter-fran').selectOption('2024')
  await page.getByTestId('filter-typ').selectOption('rostsumma')
  await expect(page).toHaveURL(/typ=rostsumma/)

  // KF 2024-03-25 § 25: rösterna är 41, närvarolistan anger 42 beslutande.
  const text = '§ 25, votering 1: rösterna är 28 ja, 12 nej och 1 avstår, sammanlagt 41. Närvarolistan anger 42 beslutande vid paragrafen.'
  const avvikelse = page.getByTestId('protokollavvikelse').filter({ hasText: text })
  await expect(avvikelse).toHaveCount(1)
  await expect(avvikelse.getByTestId('status')).toHaveText('Ny')
  await expect(avvikelse.getByTestId('sida')).toHaveAttribute('href', /#page=14$/)

  // Sammanställningen att skicka till nämndsekreteraren.
  const protokoll = page.getByTestId('protokollavvikelser').filter({ has: avvikelse })
  await protokoll.getByText('Sammanställning till nämndsekreteraren').click()
  await expect(protokoll.getByTestId('sammanstallning')).toContainText('Protokoll: Kommunfullmäktige 2024-03-25')
  await expect(protokoll.getByTestId('sammanstallning')).toContainText(`sidan 14: ${text}`)
  await expect(protokoll.getByTestId('kopiera')).toBeVisible()

  await avvikelse.getByTestId('andra-status').click()
  await avvikelse.getByTestId('ny-status').selectOption('anmald')
  await avvikelse.getByTestId('statusdatum').fill('2026-11-20')
  await avvikelse.getByTestId('ny-anteckning').fill('Skickat till nämndsekreteraren.')
  await avvikelse.getByTestId('spara-status').click()
  await expect(avvikelse.getByTestId('status')).toHaveText('Anmäld till kommunen 20 nov 2026')

  // Utgivaren ser statusen men kan inte ändra den. Den gamla adressen styrs om.
  await page.request.post('/api/auth/test/utgivare')
  await page.goto('/politik/protokollavvikelser?organ=KF&fran=2024&status=anmald')
  await expect(page).toHaveURL(/\/redaktion\/att-anmala\?organ=KF&fran=2024&status=anmald$/)
  const sedd = page.getByTestId('protokollavvikelse').filter({ hasText: text })
  await expect(sedd.getByTestId('status')).toContainText('Anmäld till kommunen')
  await expect(sedd.getByTestId('anteckning')).toHaveText('Skickat till nämndsekreteraren.')
  await expect(page.getByTestId('andra-status')).toHaveCount(0)
  await expect(page.getByTestId('sammanstallning')).toHaveCount(0)
})

test('Att anmäla är dold för läsare, i navigeringen, på sidan och i API:t', async ({ page }) => {
  for (const roll of [null, 'lasare']) {
    await page.request.post('/api/auth/logga-ut')
    if (roll) await page.request.post(`/api/auth/test/${roll}`)
    await page.goto('/politik/avvikelser')
    await expect(page.getByRole('heading', { name: 'Avvikelser', level: 1 })).toBeVisible()
    await expect(page.getByRole('link', { name: 'Att anmäla' })).toHaveCount(0)
    await page.goto('/redaktion/att-anmala')
    await expect(page.getByTestId('ej-behorig')).toBeVisible()
    await expect(page.getByTestId('protokollavvikelse')).toHaveCount(0)
    expect((await page.request.get('/api/protokollavvikelser')).status()).toBe(roll ? 403 : 401)
  }
})
