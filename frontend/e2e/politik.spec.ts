import { expect, test } from '@playwright/test'
import { API_PORT } from '../playwright.config'

test.beforeAll(async ({ request }) => {
  test.setTimeout(180_000) // insamlingen tolkar ett femtiotal protokoll
  // Kör insamlingen mot de inspelade svaren från harnosand.se: två protokoll per sida och årsmapp
  // för vart och ett av de fem organen.
  const api = `http://127.0.0.1:${API_PORT}`
  expect((await request.post(`${api}/api/auth/test/redaktor`)).ok()).toBeTruthy()
  expect((await request.post(`${api}/api/insamlingar`)).ok()).toBeTruthy()
})

test('från sammanträdeslistan till ett sammanträde och en behandling, med källa och markering', async ({ page }) => {
  await page.goto('/')
  await page.getByRole('navigation', { name: 'Huvudvyer' }).getByRole('link', { name: 'Politik och beslut' }).click()
  await expect(page.getByRole('heading', { name: 'Politik och beslut', level: 1 })).toBeVisible()

  // Läsning är öppen utan inloggning.
  await expect(page.getByTestId('anvandare').getByRole('button', { name: 'Logga in' })).toBeVisible()

  // Fem organ, 2026 från organens sidor och 2022–2025 ur arkiven.
  // Samhällsnämndens två protokoll på sidan är samma sammanträde (hela protokollet och § 145).
  await expect(page.getByTestId('sammantrade')).toHaveCount(49)
  await expect(page.getByRole('heading', { level: 2 })).toHaveText(['2026', '2025', '2024', '2023', '2022'])

  await page.getByTestId('organ').selectOption('KF')
  await expect(page.getByTestId('sammantrade')).toHaveCount(10)
  const rad = page.locator('[data-testid="sammantrade"][data-datum="2026-02-23"]')
  await expect(rad).toContainText('Kommunfullmäktige')
  await expect(rad).toContainText('13:15–15:10')
  await expect(rad).toContainText('§§ 1–14')
  await expect(rad.getByTestId('automatiskt-tolkad')).toBeVisible()

  await rad.getByRole('link').click()
  await expect(page).toHaveURL(/\/politik\/sammantraden\/\d+$/)
  await expect(page.getByRole('heading', { name: 'Kommunfullmäktige', level: 1 })).toBeVisible()
  await expect(page.getByTestId('sammantradesinfo')).toContainText('23 februari 2026')
  await expect(page.getByTestId('sammantradesinfo')).toContainText('Kommunfullmäktigesalen i Rådhuset')
  await expect(page.getByTestId('automatiskt-tolkad')).toContainText('Automatiskt tolkad, ej granskad')
  const kallrad = page.getByTestId('kallrad')
  await expect(kallrad.getByTestId('original')).toHaveAttribute('href', /^https:\/\/harnosand\.se\/download\//)
  await expect(kallrad.getByTestId('kopia')).toHaveAttribute('href', /^\/api\/dokument\/\d+$/)
  await expect(page.getByTestId('paragrafprotokoll')).toHaveCount(0)

  await expect(page.getByTestId('behandling')).toHaveCount(14)
  const beslutande = page.getByTestId('narvaro-beslutande')
  await expect(beslutande.getByRole('row', { name: /Lennart Molin/ })).toContainText('Tjänstgör för Nina Skyttberg (S)')
  await expect(beslutande.getByRole('row', { name: /Carl-Fredrik Edgren/ })).toContainText('Beslutande vid')
  await expect(page.getByTestId('narvaro-franvarande').getByRole('row', { name: /Nina Skyttberg/ })).toBeVisible()

  await page.locator('[data-testid="behandling"][data-paragraf="3"]').getByRole('link').click()
  await expect(page).toHaveURL(/\/paragraf\/3$/)
  await expect(page.getByRole('heading', { level: 1 })).toHaveText('Allmänhetens frågestund i kommunfullmäktige 2026')
  await expect(page.getByTestId('beslut')).toContainText('att anse frågan besvarad')
  await expect(page.getByTestId('diarienummer')).toContainText('2026-000025')
  await expect(page.getByTestId('kallrad')).toContainText('§ 3')

  // Bläddra till nästa paragraf, och dela länken.
  await page.getByTestId('nasta').click()
  await expect(page).toHaveURL(/\/paragraf\/4$/)
  await page.reload()
  await expect(page.getByRole('heading', { level: 1 })).toHaveText('Information från revisionen 2026')
})

test('organ- och årsfiltret speglas i URL:en', async ({ page }) => {
  await page.goto('/politik')
  await page.getByTestId('organ').selectOption('SAM')
  await expect(page).toHaveURL(/organ=SAM/)
  await expect(page.getByTestId('sammantrade')).toHaveCount(9)
  await page.getByTestId('ar').selectOption('2023')
  await expect(page).toHaveURL(/ar=2023/)
  await expect(page.getByTestId('sammantrade')).toHaveCount(2)
  await expect(page.getByRole('heading', { level: 2 })).toHaveText(['2023'])
  await page.reload()
  await expect(page.getByTestId('organ')).toHaveValue('SAM')
  await expect(page.getByTestId('ar')).toHaveValue('2023')
  await expect(page.getByTestId('sammantrade')).toHaveCount(2)
})

test('sökning på diarienummer hittar ärendet i flera organ', async ({ page }) => {
  await page.goto('/politik')
  await page.getByTestId('sok').fill('2024-000533')
  await page.getByTestId('sok').press('Enter')
  await expect(page).toHaveURL(/q=2024-000533/)
  const resultat = page.getByTestId('sokresultat')
  await expect(resultat.getByRole('heading', { level: 2 })).toContainText('2 behandlingar')
  const traffar = resultat.getByTestId('soktraff')
  await expect(traffar).toHaveCount(2)
  await expect(traffar.nth(0)).toContainText('Kommunfullmäktige')
  await expect(traffar.nth(1)).toContainText('Kommunstyrelsen')
  // Sammanträdeslistan visas inte under en sökning.
  await expect(page.getByTestId('sammantrade')).toHaveCount(0)

  await page.reload()
  await expect(page.getByTestId('sok')).toHaveValue('2024-000533')
  await traffar.nth(0).getByRole('link').click()
  await expect(page).toHaveURL(/\/paragraf\/23$/)
  await expect(page.getByRole('heading', { level: 1 })).toContainText('Hemställan om godkännande av budgetavvikelse')

  // En sökning utan träffar säger det.
  await page.goto('/politik?q=finnsintenagonstans')
  await expect(page.getByTestId('sokresultat')).toContainText('Inga behandlingar matchar sökningen.')
})

test('avvikelser vid tolkningen visas på sammanträdet', async ({ page }) => {
  await page.goto('/politik?organ=KF')
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

test('ett sammanträde ur ett paragrafprotokoll säger det', async ({ page }) => {
  await page.route(/\/api\/sammantraden\/\d+$/, async (route) => {
    const svar = await route.fetch()
    const data = await svar.json()
    data.protokoll.typ = 'paragrafprotokoll'
    await route.fulfill({ response: svar, json: data })
  })
  await page.goto('/politik?organ=KF')
  await page.locator('[data-testid="sammantrade"][data-datum="2026-03-23"]').getByRole('link').click()
  await expect(page.getByTestId('paragrafprotokoll')).toContainText('ersätts när hela protokollet publiceras')
})
