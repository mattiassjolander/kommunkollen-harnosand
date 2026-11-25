import { expect, test } from '@playwright/test'
import { API_PORT } from '../playwright.config'

// Motstridigheter i styrande dokument (#151): en redaktör läser in ett förslag, en utgivare granskar och publicerar
// det, och läsaren ser det på dokumentsidan, i listan och i den samlade listan. Förslaget är testdata med ett citat ur
// det inspelade attestreglementet (STYRANDE_URVAL=1).

const api = `http://127.0.0.1:${API_PORT}`
const ATTEST = '18.580e43d7163221b2781b73fc'
const FORSLAG = {
  motstridigheter: [
    {
      typ: 'felaktig_hanvisning',
      forklaring: 'Innehållsförteckningen anger avsnittet Krav inför attest (s. 2). Testdata för söm 2.',
      citat: [{ dokument: ATTEST, sida: 2, text: '2 Krav inför attest' }],
      uppgift: { text: 'Reglementet har avsnitt 1–7 i innehållsförteckningen.', dokument: ATTEST, sida: 2 },
    },
  ],
}

test.beforeAll(async ({ request }) => {
  test.setTimeout(120_000)
  expect((await request.post(`${api}/api/auth/test/redaktor`)).ok()).toBeTruthy()
  expect((await request.post(`${api}/api/insamlingar?kalla=harnosand-styrande-dokument`)).ok()).toBeTruthy()
  const svar = await request.post(`${api}/api/motstridigheter`, { data: FORSLAG })
  expect(svar.ok(), await svar.text()).toBeTruthy()
})

test('ett förslag granskas och publiceras av en utgivare och syns sedan märkt Analys', async ({ page }) => {
  // Utkastet syns inte för läsaren.
  await page.goto('/politik/styrande-dokument/motstridigheter')
  await expect(page.getByRole('heading', { name: 'Motstridigheter', level: 1 })).toBeVisible()
  await expect(page.getByTestId('inga')).toBeVisible()

  // En utgivare som inte läst in förslaget granskar och publicerar det.
  await page.request.post('/api/auth/test/utgivare')
  await page.goto('/redaktion/motstridigheter?typ=felaktig_hanvisning')
  const forslag = page.getByTestId('forslag').filter({ hasText: 'Krav inför attest' })
  await expect(forslag).toHaveCount(1)
  await expect(forslag).toContainText('Inläst av test-redaktor@kommunkollen.test')
  await expect(forslag).toContainText('Analys')
  await forslag.getByTestId('granska').click()
  await expect(forslag.getByTestId('granskning')).toContainText('Granskad')
  await forslag.getByTestId('publicera').click()
  await expect(forslag).toHaveCount(0)

  // Läsaren: dokumentsidan, listan och den samlade listan.
  await page.request.post('/api/auth/logga-ut')
  await page.goto('/politik/styrande-dokument?giltighet=alla')
  const rad = page.getByTestId('styrdokument').filter({ hasText: 'Attestreglemente' })
  await expect(rad.getByTestId('antal-motstridigheter')).toHaveText('1 Analys')
  await rad.getByRole('link', { name: 'Attestreglemente' }).click()
  const avsnitt = page.getByTestId('motstridigheter')
  const m = avsnitt.getByTestId('motstridighet')
  await expect(m).toHaveCount(1)
  await expect(m).toContainText('Felaktig hänvisning')
  await expect(m).toContainText('Analys')
  await expect(m.getByTestId('motstridighetsstatus')).toHaveText('Ny')
  await expect(m.getByTestId('citat')).toContainText('”2 Krav inför attest”')
  await expect(m.getByTestId('citat')).toContainText('Attestreglemente, version 1, s. 2')
  expect(await m.getByRole('link', { name: 'Sidan i PDF:en' }).first().getAttribute('href')).toMatch(
    /^\/api\/styrande-dokument\/\d+\/versioner\/1#page=2$/,
  )
  await expect(m).toHaveCSS('border-top-style', 'dashed')

  await avsnitt.getByRole('link', { name: 'Alla motstridigheter' }).click()
  await expect(page).toHaveURL(/\/politik\/styrande-dokument\/motstridigheter$/)
  await expect(page.getByTestId('motstridighet')).toHaveCount(1)
  await page.getByTestId('filter-typ').selectOption('motsagelse')
  await expect(page.getByTestId('inga')).toBeVisible()
  await expect(page).toHaveURL(/typ=motsagelse/)
})

test('en redaktör sätter status Anmäld till kommunen med datum', async ({ page }) => {
  await page.request.post('/api/auth/test/redaktor')
  await page.goto('/politik/styrande-dokument/motstridigheter')
  const m = page.getByTestId('motstridighet').filter({ hasText: 'Krav inför attest' })
  await m.getByTestId('andra-status').click()
  await m.getByTestId('status').selectOption('anmald')
  await m.getByTestId('datum').fill('2026-11-21')
  await m.getByRole('button', { name: 'Spara' }).click()
  await expect(m.getByTestId('motstridighetsstatus')).toHaveText('Anmäld till kommunen 21 nov 2026')
  await page.getByTestId('filter-status').selectOption('anmald')
  await expect(page.getByTestId('motstridighet')).toHaveCount(1)
  // Inga värderande ord.
  await expect(page.locator('main')).not.toContainText(/\bfel\b|brist|slarv/i)
})
