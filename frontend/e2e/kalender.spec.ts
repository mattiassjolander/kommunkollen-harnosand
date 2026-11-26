import { expect, test, type Page } from '@playwright/test'
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
  await page.goto('/politik')
  await page.getByRole('navigation', { name: 'Huvudvyer' }).getByRole('link', { name: 'Kalender' }).click()
  await expect(page).toHaveURL(/\/politik\/kalender$/)
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
  await page.goto('/politik/kalender?organ=KF')
  await page.getByTestId('manadsvy-knapp').click()
  await expect(page).toHaveURL(/vy=manad/)
  await expect(page.getByTestId('manadsrubrik').first()).toHaveText('November 2026')
  await expect(page.locator('td[data-dag="2026-11-23"]').getByTestId('manadshandelse')).toHaveAccessibleName('Kommunfullmäktige 13.15')

  await page.getByRole('button', { name: 'Föregående månad' }).click()
  await expect(page.getByTestId('manadsrubrik').first()).toHaveText('Oktober 2026')
  await expect(page.locator('td[data-dag="2026-10-15"]').getByTestId('manadshandelse')).toHaveAttribute('data-status', 'installt')
  await expect(page.locator('td[data-dag="2026-10-26"]').getByTestId('manadshandelse')).toHaveAccessibleName('Kommunfullmäktige 11.00')

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

// Organfärger, teckenförklaring och flera månader på bred skärm (#166).
const handelse = (page: Page, dag: string) =>
  page.locator(`td[data-dag="${dag}"]`).getByTestId('manadshandelse')

test('månadsvyn visar 1, 2 eller 3 månader efter bredden (#166)', async ({ page }) => {
  for (const [bredd, antal] of [
    [800, 1],
    [1000, 2],
    [1500, 3],
  ]) {
    await page.setViewportSize({ width: bredd, height: 900 })
    await page.goto('/kalender?vy=manad&manad=2026-11')
    await expect(page.getByTestId('manadsblock')).toHaveCount(antal)
    await expect(page.getByTestId('manadsrubrik').first()).toHaveText('November 2026')
  }
  await expect(page.getByTestId('manadsrubrik')).toHaveText(['November 2026', 'December 2026', 'Januari 2027'])
  // Bredden ändras medan vyn är öppen.
  await page.setViewportSize({ width: 800, height: 900 })
  await expect(page.getByTestId('manadsblock')).toHaveCount(1)
})

test('pilarna stegar en månad i taget i flermånadsläget (#166)', async ({ page }) => {
  await page.setViewportSize({ width: 1000, height: 900 })
  await page.goto('/kalender?vy=manad&organ=KF&manad=2026-10')
  await expect(page.getByTestId('manadsrubrik')).toHaveText(['Oktober 2026', 'November 2026'])
  await page.getByRole('button', { name: 'Nästa månad' }).click()
  await expect(page).toHaveURL(/manad=2026-11/)
  await expect(page.getByTestId('manadsrubrik')).toHaveText(['November 2026', 'December 2026'])
  await page.getByRole('button', { name: 'Föregående månad' }).click()
  await expect(page).toHaveURL(/manad=2026-10/)
  await expect(page.getByTestId('manadsrubrik')).toHaveText(['Oktober 2026', 'November 2026'])
  // Kompakta celler: alla sammanträden syns, även i flermånadsläget.
  await expect(page.getByTestId('manadsblock').first().getByTestId('manadshandelse')).not.toHaveCount(0)
  for (const h of await page.getByTestId('manadshandelse').all()) await expect(h).toBeVisible()
  // Pilarna spärras vid den sista månaden med sammanträden: den sista visade månaden får inte passera den.
  const nasta = page.getByRole('button', { name: 'Nästa månad' })
  while (await nasta.isEnabled()) await nasta.click()
  await expect(page.getByTestId('manadsblock').last().getByTestId('manadshandelse')).not.toHaveCount(0)
})

test('händelserna har förkortning, tid, organfärg och fullt namn i title (#166)', async ({ page }) => {
  await page.setViewportSize({ width: 1000, height: 900 })
  await page.goto('/kalender?vy=manad&organ=KF&manad=2026-10')
  const kf = handelse(page, '2026-11-23')
  await expect(kf.locator('[aria-hidden="true"]')).toHaveText('KF')
  await expect(kf).toHaveAttribute('title', 'Kommunfullmäktige kl. 13.15')
  await expect(kf).toHaveAccessibleName('Kommunfullmäktige 13.15')
  // Texten i --ink, färgen bara i kantlinjen (--organ-kf = --series-1).
  const farger = await kf.evaluate((el) => {
    const rot = getComputedStyle(document.documentElement)
    const prov = document.createElement('span')
    document.body.append(prov)
    const losa = (v: string) => ((prov.style.color = v), getComputedStyle(prov).color)
    const svar = {
      text: getComputedStyle(el).color,
      kant: getComputedStyle(el).borderLeftColor,
      ink: losa(rot.getPropertyValue('--ink')),
      serie: losa(rot.getPropertyValue('--series-1')),
    }
    prov.remove()
    return svar
  })
  expect(farger.text).toBe(farger.ink)
  expect(farger.kant).toBe(farger.serie)
  await expect(kf).toHaveCSS('text-decoration-line', 'none')
  await kf.hover()
  await expect(kf).toHaveCSS('text-decoration-line', 'underline')

  // Inställt: överstruket och "(inställt)" för skärmläsare.
  const installt = handelse(page, '2026-10-15')
  await expect(installt).toHaveAttribute('data-status', 'installt')
  await expect(installt).toHaveCSS('text-decoration-line', 'line-through')
  await expect(installt).toHaveAttribute('title', /\(inställt\)$/)
  await expect(installt).toHaveAccessibleName(/Kommunfullmäktige .*\(inställt\)$/)

  // Listvyn: färgmarkering vid det fulla namnet.
  await page.getByRole('button', { name: 'Lista' }).click()
  const namn = page.getByTestId('kommande').getByTestId('kalenderhandelse').first().locator('strong')
  await expect(namn).toHaveText('Kommunfullmäktige')
  await expect(namn).toHaveCSS('border-left-style', 'solid')
  expect(await namn.evaluate((el) => getComputedStyle(el).borderLeftColor)).toBe(farger.serie)
})

test('teckenförklaringen filtrerar och speglar organ i URL:en (#166)', async ({ page }) => {
  await page.setViewportSize({ width: 1500, height: 900 })
  await page.goto('/kalender?vy=manad&manad=2026-11')
  const forklaring = page.getByTestId('teckenforklaring')
  await expect(forklaring.getByRole('button')).toHaveText([
    'KF Kommunfullmäktige',
    'KS Kommunstyrelsen',
    'SAM Samhällsnämnden',
    'SOC Socialnämnden',
    'SKOL Skolnämnden',
  ])
  const organ = new Set(await page.getByTestId('manadshandelse').evaluateAll((l) => l.map((e) => e.dataset.organ)))
  expect(organ.size).toBeGreaterThan(1)

  const ks = forklaring.getByRole('button', { name: 'KS Kommunstyrelsen' })
  await ks.click()
  await expect(page).toHaveURL(/organ=KS/)
  await expect(ks).toHaveAttribute('aria-pressed', 'true')
  await expect(page.getByTestId('organfilter')).toHaveValue('KS')
  await expect(page.getByTestId('manadshandelse').first()).toBeVisible()
  expect(new Set(await page.getByTestId('manadshandelse').evaluateAll((l) => l.map((e) => e.dataset.organ)))).toEqual(
    new Set(['KS']),
  )

  // Ett nytt klick på samma organ tar bort filtret.
  await ks.click()
  await expect(page).not.toHaveURL(/organ=/)
  await expect(ks).toHaveAttribute('aria-pressed', 'false')
  await expect(page.getByTestId('organfilter')).toHaveValue('')
  expect(new Set(await page.getByTestId('manadshandelse').evaluateAll((l) => l.map((e) => e.dataset.organ))).size).toBe(
    organ.size,
  )
})

test('ett okänt organ får neutral markering och sitt id i versaler (#166)', async ({ page }) => {
  await page.route('**/api/kalender', async (route) => {
    const svar = await route.fetch()
    const k = await svar.json()
    const h = k.handelser.find((x: { datum: string }) => x.datum.startsWith('2026-11'))
    k.handelser.push({ ...h, id: 999_999, organ: { ...h.organ, id: 'krf', namn: 'Krisledningsnämnden' } })
    k.handelser.sort((a: { datum: string }, b: { datum: string }) => a.datum.localeCompare(b.datum))
    await route.fulfill({ response: svar, json: k })
  })
  await page.setViewportSize({ width: 800, height: 900 })
  await page.goto('/kalender?vy=manad&manad=2026-11')
  const okand = page.locator('[data-testid="manadshandelse"][data-organ="krf"]')
  await expect(okand.locator('[aria-hidden="true"]')).toHaveText('KRF')
  const [kant, muted] = await okand.evaluate((el) => {
    const prov = document.createElement('span')
    document.body.append(prov)
    prov.style.color = 'var(--ink-muted)'
    const svar = [getComputedStyle(el).borderLeftColor, getComputedStyle(prov).color]
    prov.remove()
    return svar
  })
  expect(kant).toBe(muted)
})
