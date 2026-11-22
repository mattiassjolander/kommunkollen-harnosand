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
  await expect(flikar.getByRole('link', { name: 'Kopplingar', exact: true })).toHaveCount(0)

  await page.request.post('/api/auth/test/redaktor')
  await page.reload()
  await flikar.getByRole('link', { name: 'Kopplingar', exact: true }).click()
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

test('redaktören ser sitt avvisade förslag, ändrar beslutet och ser historiken (#77)', async ({ page }) => {
  await page.request.post('/api/auth/test/redaktor')
  await page.goto('/politik/kopplingar')
  const forslag = page.getByTestId('kopplingsforslag').first()
  await expect(forslag).toBeVisible()
  const id = await forslag.getAttribute('data-koppling')
  await forslag.getByTestId('avvisa').click()
  await expect(page.getByTestId('beslutade').getByTestId('kopplingsstatus')).toHaveAttribute('data-status', 'avvisad')

  // Avvisade, bara mina beslut: förslaget finns där med beslutsfattare och tid.
  await page.getByTestId('flik-avvisad').click()
  await expect(page).toHaveURL(/status=avvisad/)
  await page.getByTestId('mina-beslut').check()
  await expect(page).toHaveURL(/mina=1/)
  const kort = page.locator(`[data-testid="beslutad-koppling"][data-koppling="${id}"]`)
  await expect(kort.getByTestId('beslutsfattare')).toContainText('Beslutat av test-redaktor@kommunkollen.test')
  await expect(kort.getByTestId('historik').locator('li')).toHaveCount(1)

  // Ändra beslutet: motivering krävs.
  await kort.getByTestId('andra-beslut').click()
  const formular = kort.getByTestId('andra-formular')
  await formular.getByLabel('Bekräfta').check()
  await formular.getByTestId('motivering').fill('Hänvisningen gäller samma ärende.')
  await formular.getByTestId('spara-beslut').click()
  await expect(kort.getByTestId('kopplingsstatus')).toHaveAttribute('data-status', 'bekraftad')
  const historik = kort.getByTestId('historik').locator('li')
  await expect(historik).toHaveCount(2)
  await expect(historik.nth(0)).toContainText('Avvisad av test-redaktor@kommunkollen.test')
  await expect(historik.nth(1)).toContainText('Bekräftad av test-redaktor@kommunkollen.test')
  await expect(historik.nth(1)).toContainText('”Hänvisningen gäller samma ärende.”')

  // Kopplingen ligger nu under Bekräftade, och ärendevyn länkar tillbaka till beslutet.
  await page.getByTestId('flik-bekraftad').click()
  const bekraftad = page.locator(`[data-testid="beslutad-koppling"][data-koppling="${id}"]`)
  await expect(bekraftad).toBeVisible()
  await bekraftad.getByRole('link').last().click()
  await expect(page).toHaveURL(/\/paragraf\/\d+$/)
  await page.getByTestId('arendelank').click()
  await page.locator(`[data-testid="till-beslut"][href$="koppling=${id}"]`).click()
  await expect(page).toHaveURL((u) => u.pathname === '/politik/kopplingar' && u.search === `?status=bekraftad&koppling=${id}`)
  await expect(page.locator(`#koppling-${id}`)).toHaveClass(/vald/)
  await page.request.post('/api/auth/logga-ut')
})
