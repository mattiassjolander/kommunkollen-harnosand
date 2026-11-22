import { expect, test } from '@playwright/test'
import { API_PORT } from '../playwright.config'

const api = `http://127.0.0.1:${API_PORT}`

// Backend kör med dagens datum låst till 2026-11-20 (playwright.config.ts).
test.use({ permissions: ['clipboard-read', 'clipboard-write'] })

test.beforeAll(async ({ request }) => {
  test.setTimeout(300_000) // insamlingen tolkar fullmäktiges protokoll
  // Förbered data: fullmäktiges protokoll och de fem organens sammanträdesplaner (#68).
  expect((await request.post(`${api}/api/auth/test/redaktor`)).ok()).toBeTruthy()
  for (const kalla of ['harnosand-protokoll-kf', 'harnosand-sammantradesplaner']) {
    expect((await request.post(`${api}/api/insamlingar?kalla=${kalla}`)).ok()).toBeTruthy()
  }
})

test('kalendern listar kommande sammanträden med prenumeration och ics per sammanträde (#68)', async ({ page }) => {
  await page.goto('/')
  await page.getByRole('navigation', { name: 'Huvudvyer' }).getByRole('link', { name: 'Kalender' }).click()
  await expect(page).toHaveURL(/\/kalender$/)
  await expect(page.getByRole('heading', { name: 'Kalender', level: 1 })).toBeVisible()
  // Ingen inloggning krävs för att läsa.
  await expect(page.getByTestId('anvandare').getByRole('button', { name: 'Logga in' })).toBeVisible()

  // Alla organ: flödet "alla".
  const pren = page.getByTestId('prenumerera')
  await expect(pren).toHaveAttribute('data-flode', 'alla')
  await expect(pren.getByTestId('webcal')).toHaveAttribute('href', /^webcal:\/\/127\.0\.0\.1:\d+\/kalender\/alla\.ics$/)

  await page.getByTestId('organfilter').selectOption('KF')
  await expect(page).toHaveURL(/organ=KF/)
  await expect(pren).toHaveAttribute('data-flode', 'kommunfullmaktige')
  await expect(pren.getByTestId('webcal')).toHaveAttribute('href', /\/kalender\/kommunfullmaktige\.ics$/)
  await expect(pren.getByTestId('google')).toHaveAttribute(
    'href',
    /^https:\/\/calendar\.google\.com\/calendar\/r\?cid=webcal%3A%2F%2F.+kommunfullmaktige\.ics$/,
  )
  await pren.getByTestId('kopiera').click()
  await expect(pren.getByTestId('kopierad')).toBeVisible()
  expect(await page.evaluate(() => navigator.clipboard.readText())).toMatch(/^http:\/\/.+\/kalender\/kommunfullmaktige\.ics$/)

  const kommande = page.getByTestId('kommande').getByTestId('kalenderhandelse')
  await expect(kommande).toHaveCount(2) // 23 november och 14 december
  const dec = page.locator('[data-testid="kalenderhandelse"][data-datum="2026-12-14"]')
  await expect(dec).toContainText('kl. 13.15–ca')
  await expect(dec).toContainText('(enligt senaste protokollet)')
  // Fullmäktige webbsänds: före sammanträdet länkar kalendern till sidan för webb-tv (#68, del 3).
  await expect(dec.getByTestId('webbsandning')).toHaveText('Webb-tv')
  await expect(dec.getByTestId('webbsandning')).toHaveAttribute('href', /kommunfullmaktige\/webb-tv\.html$/)

  // Ett sammanträde som .ics-fil.
  const nedladdning = page.waitForEvent('download')
  await dec.getByTestId('ladda-ner-ics').click()
  const fil = await nedladdning
  expect(fil.suggestedFilename()).toBe('kommunfullmaktige-2026-12-14.ics')

  // Tidigare sammanträden: inställda är överstrukna, hållna har protokoll.
  await page.getByText(/^Tidigare sammanträden/).click()
  const installt = page.getByTestId('tidigare').locator('[data-datum="2026-10-15"]')
  await expect(installt).toHaveAttribute('data-status', 'installt')
  await expect(installt.locator('strong')).toHaveCSS('text-decoration-line', 'line-through')
  await expect(installt).toContainText('Inställt')
  // Efter sammanträdet: kungörelsen och inspelningen.
  const mars = page.getByTestId('tidigare').locator('[data-datum="2026-03-23"]')
  await expect(mars.getByTestId('kallelse')).toHaveText('Kungörelse')
  await expect(mars.getByTestId('webbsandning')).toHaveAttribute('href', /^https:\/\/qcnl\.tv\/p\//)
  // e2e läser två av fullmäktiges protokoll (februari och mars).
  await page.getByTestId('tidigare').locator('[data-datum="2026-03-23"]').getByRole('link', { name: 'Protokoll' }).click()
  await expect(page).toHaveURL(/\/politik\/sammantraden\/\d+$/)
})

test('månadsvyn visar sammanträdena per dag (#68)', async ({ page }) => {
  await page.goto('/kalender?organ=KF')
  await page.getByTestId('manadsvy-knapp').click()
  await expect(page).toHaveURL(/vy=manad/)
  await expect(page.getByTestId('manadsrubrik')).toHaveText('November 2026')
  await expect(page.locator('td[data-dag="2026-11-23"]').getByTestId('manadshandelse')).toContainText('Kommunfullmäktige 13.15')

  await page.getByRole('button', { name: 'Föregående månad' }).click()
  await expect(page.getByTestId('manadsrubrik')).toHaveText('Oktober 2026')
  await expect(page.locator('td[data-dag="2026-10-15"]').getByTestId('manadshandelse')).toHaveAttribute('data-status', 'installt')
  await expect(page.locator('td[data-dag="2026-10-26"]').getByTestId('manadshandelse')).toContainText('Kommunfullmäktige 11.00')

  // Ett sammanträde i månadsvyn öppnas i listan.
  await page.locator('td[data-dag="2026-10-26"]').getByTestId('manadshandelse').first().click()
  await expect(page).toHaveURL(/sammantrade=\d+/)
  await expect(page.locator('.handelse.vald')).toHaveAttribute('data-datum', '2026-10-26')
})

test('kalenderflödet är öppet och ges som text/calendar', async ({ request }) => {
  const svar = await request.get('/kalender/alla.ics')
  expect(svar.ok()).toBeTruthy()
  expect(svar.headers()['content-type']).toContain('text/calendar')
  const text = await svar.text()
  expect(text.startsWith('BEGIN:VCALENDAR\r\n')).toBeTruthy()
  expect(text).toContain('STATUS:CANCELLED')
  expect(text).toContain('TZID:Europe/Stockholm')
})
