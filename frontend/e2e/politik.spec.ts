import { expect, test } from '@playwright/test'
import { API_PORT } from '../playwright.config'

test.beforeAll(async ({ request }) => {
  // Kör insamlingen av KF:s protokoll mot de inspelade svaren från harnosand.se.
  const api = `http://127.0.0.1:${API_PORT}`
  expect((await request.post(`${api}/api/auth/test/redaktor`)).ok()).toBeTruthy()
  expect((await request.post(`${api}/api/insamlingar?kalla=harnosand-protokoll-kf`)).ok()).toBeTruthy()
})

test('från sammanträdeslistan till ett sammanträde och en behandling, med källa och markering', async ({ page }) => {
  await page.goto('/')
  await page.getByRole('navigation', { name: 'Huvudvyer' }).getByRole('link', { name: 'Politik och beslut' }).click()
  await expect(page.getByRole('heading', { name: 'Politik och beslut', level: 1 })).toBeVisible()

  // Läsning är öppen utan inloggning.
  await expect(page.getByTestId('anvandare').getByRole('button', { name: 'Logga in' })).toBeVisible()

  const rader = page.getByTestId('sammantrade')
  await expect(rader).toHaveCount(8)
  const rad = page.locator('[data-testid="sammantrade"][data-datum="2026-09-28"]')
  await expect(rad).toContainText('Kommunfullmäktige')
  await expect(rad).toContainText('13:15–16:30')
  await expect(rad).toContainText('§§ 121–136')
  await expect(rad.getByTestId('automatiskt-tolkad')).toBeVisible()

  await rad.getByRole('link').click()
  await expect(page).toHaveURL(/\/politik\/sammantraden\/\d+$/)
  await expect(page.getByRole('heading', { name: 'Kommunfullmäktige', level: 1 })).toBeVisible()
  await expect(page.getByTestId('sammantradesinfo')).toContainText('28 september 2026')
  await expect(page.getByTestId('sammantradesinfo')).toContainText('Rådhuset - KF-salen')
  await expect(page.getByTestId('automatiskt-tolkad')).toContainText('Automatiskt tolkad, ej granskad')
  const kallrad = page.getByTestId('kallrad')
  await expect(kallrad.getByTestId('original')).toHaveAttribute('href', /^https:\/\/harnosand\.se\/download\//)
  await expect(kallrad.getByTestId('kopia')).toHaveAttribute('href', /^\/api\/dokument\/\d+$/)

  await expect(page.getByTestId('behandling')).toHaveCount(16)
  const beslutande = page.getByTestId('narvaro-beslutande')
  await expect(beslutande.getByRole('row', { name: /Carl-Fredrik Edgren/ })).toContainText('partilös')
  await expect(beslutande.getByRole('row', { name: /Hans Rosengren/ })).toContainText('parti anges inte i protokollet')
  await expect(beslutande.getByRole('row', { name: /Mohamed Abdulwahab Mohamed/ })).toContainText(
    'Tjänstgör för Knapp Britta Thyr (MP) · Beslutande vid § 129',
  )
  await expect(beslutande.getByRole('row', { name: /^Knapp Britta Thyr/ })).toContainText('Jäv § 129')

  await page.locator('[data-testid="behandling"][data-paragraf="129"]').getByRole('link').click()
  await expect(page).toHaveURL(/\/paragraf\/129$/)
  await expect(page.getByRole('heading', { level: 1 })).toHaveText(
    'Svar på Hemställan om lånefinansiering för inköp av ombordutrustning',
  )
  await expect(page.getByTestId('beslut')).toContainText('upptar lån om högst 22 mkr')
  await expect(page.getByTestId('jav')).toContainText('Knapp Britta Thyr (MP)')
  await expect(page.getByTestId('beslutande').getByTestId('person').filter({ hasText: /^\s*Knapp Britta Thyr/ })).toHaveCount(0)
  await expect(page.getByTestId('kallrad')).toContainText('§ 129')

  // Bläddra till nästa paragraf, och dela länken.
  await page.getByTestId('nasta').click()
  await expect(page).toHaveURL(/\/paragraf\/130$/)
  await page.reload()
  await expect(page.getByRole('heading', { level: 1 })).toHaveText('Svar på återremiss gällande sammanträdestider 2027')
})

test('organfiltret speglas i URL:en', async ({ page }) => {
  await page.goto('/politik')
  await page.getByTestId('organ').selectOption('KF')
  await expect(page).toHaveURL(/organ=KF/)
  await expect(page.getByTestId('sammantrade')).toHaveCount(8)
  await page.reload()
  await expect(page.getByTestId('organ')).toHaveValue('KF')
})

test('avvikelser vid tolkningen visas på sammanträdet', async ({ page }) => {
  await page.goto('/politik')
  await page.locator('[data-testid="sammantrade"][data-datum="2026-03-23"]').getByRole('link').click()
  await expect(page.getByTestId('avvikelser')).toContainText('saknas: 53, 54')
})

test('ett protokoll som inte gick att tolka visas med markering', async ({ page }) => {
  await page.route('**/api/sammantraden', async (route) => {
    const svar = await route.fetch()
    const data = await svar.json()
    data[0].tolkning = 'ej_tolkad'
    await route.fulfill({ response: svar, json: data })
  })
  await page.goto('/politik')
  await expect(page.getByTestId('sammantrade').first().getByTestId('ej-tolkad')).toContainText(
    'Kunde inte tolkas automatiskt',
  )
})
