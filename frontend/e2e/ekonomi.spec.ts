import { expect, test } from '@playwright/test'
import { API_PORT } from '../playwright.config'

test.beforeAll(async ({ request }) => {
  // Förbered data: logga in som redaktör och kör en insamling mot de inspelade Kolada-svaren.
  const api = `http://127.0.0.1:${API_PORT}`
  expect((await request.post(`${api}/api/auth/test/redaktor`)).ok()).toBeTruthy()
  expect((await request.post(`${api}/api/insamlingar`)).ok()).toBeTruthy()
})

test('ekonomivyn är öppen och visar årets resultat som tidsserie med källrad', async ({ page }) => {
  await page.goto('/ekonomi')

  // Ingen inloggning krävs för att läsa.
  await expect(page.getByTestId('anvandare').getByRole('button', { name: 'Logga in' })).toBeVisible()

  const kort = page.locator('[data-matt="kolada:N03007"]')
  await expect(kort.getByRole('heading', { name: 'Årets resultat kommun, kr/inv' })).toBeVisible()

  // Standardvisning från 2022: 2022–2025 i inspelningen.
  await expect(kort.getByTestId('stapel')).toHaveCount(4)

  const kallrad = kort.getByTestId('kallrad')
  await expect(kallrad).toContainText('Kolada')
  await expect(kallrad).toContainText('N03007')
  await expect(kallrad).toContainText('Avser 2022–2025')
  await expect(kallrad).toContainText('Publicerad 28 aug 2026')

  // Tooltip vid hover visar år, värde med enhet och källa.
  const yta = kort.locator('rect.traffyta').last()
  await yta.hover()
  const tips = page.getByRole('tooltip')
  await expect(tips).toContainText('2025')
  await expect(tips).toContainText('972 kr/inv')
  await expect(tips).toContainText('Kolada')
})

test('redaktör kan logga in och ut och stannar på sidan', async ({ page }) => {
  await page.goto('/ekonomi')
  await page.getByTestId('anvandare').getByRole('button', { name: 'Logga in' }).click()

  // Läsare finns inte som val när läsning är öppen.
  await expect(page.getByRole('button', { name: 'Logga in som läsare (test)' })).toHaveCount(0)
  await page.getByRole('button', { name: 'Logga in som redaktör (test)' }).click()
  await expect(page.getByTestId('anvandare')).toContainText('Test (redaktor)')
  await expect(page.getByTestId('nyckeltal').first()).toBeVisible()

  await page.getByRole('button', { name: 'Logga ut' }).click()
  await expect(page.getByTestId('anvandare').getByRole('button', { name: 'Logga in' })).toBeVisible()
  await expect(page.getByTestId('nyckeltal').first()).toBeVisible()
})

test('man kan avbryta inloggningen och fortsätta läsa', async ({ page }) => {
  await page.goto('/ekonomi')
  await page.getByTestId('anvandare').getByRole('button', { name: 'Logga in' }).click()
  await page.getByRole('button', { name: 'Fortsätt utan att logga in' }).click()
  await expect(page.getByTestId('nyckeltal').first()).toBeVisible()
})

test('ej behörigt Google-konto får ett tydligt meddelande', async ({ page }) => {
  await page.goto('/?fel=ej-behorig')
  await expect(page.getByTestId('inloggningsfel')).toContainText('har inte åtkomst')
})

test('ett nyckeltal kan växlas mellan diagram och tabell', async ({ page }) => {
  await page.goto('/ekonomi')
  const kort = page.locator('[data-matt="scb:BalansKnN:065"]')
  await expect(kort.getByRole('heading', { name: 'Likvida medel' })).toBeVisible()
  await expect(kort.getByTestId('stapel').first()).toBeVisible()

  await kort.getByRole('button', { name: 'Tabell' }).click()
  await expect(kort.getByTestId('stapel')).toHaveCount(0)
  const tabell = kort.getByRole('table')
  await expect(tabell.getByRole('columnheader', { name: 'mnkr' })).toBeVisible() // tkr från SCB visas i mnkr
  await expect(tabell.getByRole('row')).toHaveCount(1 + 4) // rubrik + 2022–2025

  const kallrad = kort.getByTestId('kallrad')
  await expect(kallrad).toContainText('SCB')
  await expect(kallrad).toContainText('BalansKnN, post 065')
  await expect(kallrad).toContainText('Löpande priser')
})

test('visningen startar 2022 men kan börja tidigare, och valet speglas i URL:en', async ({ page }) => {
  await page.goto('/ekonomi')
  const kort = page.locator('[data-matt="scb:BalansKnN:065"]')
  await expect(kort.getByTestId('stapel')).toHaveCount(4)

  await page.getByTestId('fran-ar').selectOption('1998')
  await expect(page).toHaveURL(/fran=1998/)
  await expect(kort.getByTestId('stapel')).toHaveCount(2025 - 1998 + 1)

  await page.reload()
  await expect(page.getByTestId('fran-ar')).toHaveValue('1998')
})

test('ett reviderat värde markeras med ↻ och tooltipen visar tidigare och nytt värde', async ({ page }) => {
  // Revideringen läggs in i API-svaret. Själva versionshanteringen testas i backend (söm 1).
  await page.route('**/api/ekonomi*', async (route) => {
    const svar = await route.fetch()
    const data = await svar.json()
    for (const g of data.grupper)
      for (const n of g.nyckeltal)
        if (n.id === 'scb:BalansKnN:065') {
          const p = n.serie.punkter.find((p: { period: string }) => p.period === '2024')
          p.historik = [{ ...p, varde: p.varde - 12000, version: 1 }]
          p.version = 2
          p.reviderad = true
          p.senast_andrad = '2026-11-01T02:15:00Z'
        }
    await route.fulfill({ response: svar, json: data })
  })
  await page.goto('/ekonomi')
  const kort = page.locator('[data-matt="scb:BalansKnN:065"]')
  await expect(kort.getByTestId('reviderad')).toHaveCount(1)

  // Diagrammet: tooltip vid hover på 2024.
  await kort.locator('rect.traffyta').nth(2).hover()
  await expect(kort.getByRole('tooltip')).toContainText('2024')
  await expect(kort.getByTestId('revisionstips')).toContainText('Reviderat. Tidigare')
  await expect(kort.getByRole('tooltip')).toContainText('Ändrat 2026-11-01')

  // Tabellen: ↻ vid värdet, tooltipen nås också med tangentbordet.
  await kort.getByRole('button', { name: 'Tabell' }).click()
  const markering = kort.getByRole('row', { name: /2024/ }).getByTestId('reviderad')
  await markering.focus()
  const tips = kort.getByTestId('revisionstips')
  await expect(tips).toContainText('Tidigare:')
  await expect(tips).toContainText('Nytt:')
  await expect(tips).toContainText('Ändrat 2026-11-01')
  await expect(tips).toContainText('SCB')
  await expect(markering).toHaveAttribute('aria-label', /Tidigare .* mnkr, nu .* mnkr/)
})

// Analysverktyg (#10)

test('period, jämförelse och vy speglas i URL:en och återställs vid omladdning och delad länk', async ({ page, browser }) => {
  await page.goto('/ekonomi')
  await page.getByTestId('fran-ar').selectOption('2015')
  await page.getByTestId('till-ar').selectOption('2024')
  await page.getByTestId('jamfor-fran').selectOption('2018')
  await page.getByTestId('jamfor-till').selectOption('2024')
  await page.getByTestId('vy').getByRole('button', { name: 'Tabell' }).click()
  await expect(page).toHaveURL(/fran=2015/)
  await expect(page).toHaveURL(/till=2024/)
  await expect(page).toHaveURL(/jamfor=2018-2024/)
  await expect(page).toHaveURL(/vy=tabell/)

  const kontrollera = async (sida: typeof page) => {
    await expect(sida.getByTestId('fran-ar')).toHaveValue('2015')
    await expect(sida.getByTestId('till-ar')).toHaveValue('2024')
    await expect(sida.getByTestId('jamfor-fran')).toHaveValue('2018')
    await expect(sida.getByTestId('jamfor-till')).toHaveValue('2024')
    await expect(sida.getByTestId('vy').getByRole('button', { name: 'Tabell' })).toHaveAttribute('aria-pressed', 'true')
    const kort = sida.locator('[data-matt="scb:BalansKnN:065"]')
    await expect(kort.getByTestId('stapel')).toHaveCount(0)
    await expect(kort.getByRole('table').getByRole('row')).toHaveCount(1 + (2024 - 2015 + 1))
    await expect(kort.getByTestId('jamforelse')).toContainText('2018–2024:')
  }
  await page.reload()
  await kontrollera(page)

  // En delad länk i ett nytt fönster visar samma sak.
  const ny = await (await browser.newContext()).newPage()
  await ny.goto(page.url())
  await kontrollera(ny)
  await ny.context().close()
})

test('förändringen mellan två år visas i kronor och procent och större förändringar markeras', async ({ page }) => {
  await page.goto('/ekonomi?jamfor=2022-2025')
  await expect(page.getByTestId('jamforelse-info')).toContainText('minst 10 %')
  const likvida = page.locator('[data-matt="scb:BalansKnN:065"]').getByTestId('jamforelse')
  await expect(likvida).toContainText(/2022–2025:\s*\+\d+,\d mnkr\s*\(\+\d+,\d %\)/)
  await expect(likvida).toContainText('65,2 mnkr →')
  await expect(likvida).toHaveAttribute('data-stor', 'ja')
  await expect(likvida).toContainText('Större förändring')
  // Nyckeltal i procent jämförs i procentenheter.
  await expect(page.locator('[data-matt="kolada:N03106"]').getByTestId('jamforelse')).toContainText('procentenheter')
})

test('mandatperioderna syns som band i tidsdiagrammen', async ({ page }) => {
  await page.goto('/ekonomi?fran=2011')
  const band = page.locator('[data-matt="scb:BalansKnN:065"]').getByTestId('mandatperiod')
  await expect(band).toHaveCount(4)
  await expect(band.nth(0)).toHaveAttribute('data-period', '2010–2014')
  await expect(band.nth(3)).toHaveAttribute('data-period', '2022–2026')
})

test('tabelldata kan exporteras som CSV med källa och period', async ({ page }) => {
  await page.goto('/ekonomi?fran=2020&till=2023')
  const kort = page.locator('[data-matt="scb:BalansKnN:065"]')
  const [nedladdning] = await Promise.all([page.waitForEvent('download'), kort.getByTestId('csv').click()])
  expect(nedladdning.suggestedFilename()).toBe('kommunkollen-scb-BalansKnN-065-2020-2023.csv')
  const text = (await (await import('node:fs/promises')).readFile(await nedladdning.path(), 'utf-8')).replace(/^﻿/, '')
  const rader = text.trim().split(/\r\n/)
  expect(rader[0]).toBe(
    'Nyckeltal;Mått-id;Period;Värde;Enhet;Prisnivå;Källa;Källans webbplats;Publicerad av källan;Hämtad;Version',
  )
  expect(rader.slice(1).map((r) => r.split(';')[2])).toEqual(['2020', '2021', '2022', '2023'])
  expect(rader[1]).toMatch(/^Likvida medel;scb:BalansKnN:065;2020;\d+;tkr;löpande priser;SCB;https:\/\/[^;]+;\d{4}-\d{2}-\d{2};\d{4}-\d{2}-\d{2};1$/)

  const [alla] = await Promise.all([page.waitForEvent('download'), page.getByTestId('exportera-alla').click()])
  expect(alla.suggestedFilename()).toBe('kommunkollen-ekonomi-2020-2023.csv')
})
