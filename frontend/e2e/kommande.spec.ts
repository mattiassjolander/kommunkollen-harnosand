import { expect, test } from '@playwright/test'
import { API_PORT } from '../playwright.config'

const api = `http://127.0.0.1:${API_PORT}`

test.beforeAll(async ({ request }) => {
  test.setTimeout(300_000) // insamlingen tolkar protokollen
  expect((await request.post(`${api}/api/auth/test/redaktor`)).ok()).toBeTruthy()
  for (const kalla of ['harnosand-protokoll-ks', 'harnosand-protokoll-kf']) {
    expect((await request.post(`${api}/api/insamlingar?kalla=${kalla}`)).ok()).toBeTruthy()
  }
})

test('kommande ärenden: lista, filter och underlag', async ({ page }) => {
  await page.goto('/')
  await page.getByRole('navigation', { name: 'Huvudvyer' }).getByRole('link', { name: 'Kommande' }).click()
  await expect(page).toHaveURL(/\/kommande$/)
  await expect(page.getByRole('heading', { name: 'Kommande', level: 1 })).toBeVisible()

  const rader = page.getByTestId('kommande-arende')
  await expect(rader.first()).toBeVisible()

  // Filtret på status visar bara ärenden med den statusen.
  await page.getByTestId('status-motion').click()
  await expect(page).toHaveURL(/status=motion/)
  for (const status of await rader.evaluateAll((el) => el.map((e) => e.getAttribute('data-status')))) {
    expect(status).toBe('motion')
  }

  // Ett klick visar mer om ärendet, med länkar till protokollen.
  await rader.first().getByRole('button').click()
  await expect(page).toHaveURL(/arende=\d+/)
  const detalj = page.getByTestId('detalj')
  await expect(detalj).toContainText('Senaste beslutet')
  const lankar = detalj.getByTestId('protokoll-lankar').first()
  await expect(lankar.getByRole('link', { name: /harnosand\.se/ })).toHaveAttribute('href', /^https?:\/\//)
  await expect(lankar.getByRole('link', { name: /Sparad kopia/ })).toHaveAttribute('href', /^\/api\/dokument\/\d+$/)
  await detalj.getByRole('link', { name: /Visa hela ärendets väg/ }).click()
  await expect(page).toHaveURL(/\/politik\/arenden\/\d+$/)
})
