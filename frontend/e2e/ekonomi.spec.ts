import { expect, test } from '@playwright/test'
import { API_PORT } from '../playwright.config'

test.beforeAll(async ({ request }) => {
  test.setTimeout(180_000) // insamlingen tolkar ett femtiotal protokoll
  // Förbered data: logga in som redaktör och kör en insamling mot de inspelade Kolada-svaren.
  const api = `http://127.0.0.1:${API_PORT}`
  expect((await request.post(`${api}/api/auth/test/redaktor`)).ok()).toBeTruthy()
  expect((await request.post(`${api}/api/insamlingar`)).ok()).toBeTruthy()
})

test('ekonomivyn är öppen och visar årets resultat som tidsserie med källrad', async ({ page }) => {
  await page.goto('/ekonomi?enhet=inv')

  // Ingen inloggning krävs för att läsa.
  await expect(page.getByTestId('anvandare').getByRole('button', { name: 'Logga in' })).toBeVisible()

  // Årets resultat per invånare (Kolada) visas på samma kort som totalen från SCB.
  const kort = page.locator('[data-matt="scb:ResultKnN:120"]')
  await expect(kort).toHaveAttribute('data-visad', 'kolada:N03007')
  await expect(kort.getByRole('heading', { name: 'Årets resultat', exact: true })).toBeVisible()

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
    'Nyckeltal;Mått-id;Period;Värde;Enhet;Prisnivå;Källa;Källans webbplats;Publicerad av källan;Hämtad;Version;Område',
  )
  expect(rader.slice(1).map((r) => r.split(';')[2])).toEqual(['2020', '2021', '2022', '2023'])
  expect(rader[1]).toMatch(/^Likvida medel;scb:BalansKnN:065;2020;\d+;tkr;löpande priser;SCB;https:\/\/[^;]+;\d{4}-\d{2}-\d{2};\d{4}-\d{2}-\d{2};1;Härnösand$/)

  const [alla] = await Promise.all([page.waitForEvent('download'), page.getByTestId('exportera-alla').click()])
  expect(alla.suggestedFilename()).toBe('kommunkollen-ekonomi-2020-2023.csv')
})

// Översikt med huvudtal, grupper som frågor och sammanslagna kort (#80)

test('översikten visar fem huvudtal med förklaring, och ett huvudtal leder till sitt kort', async ({ page }) => {
  await page.goto('/ekonomi')
  const oversikt = page.getByTestId('huvudtal')
  const huvudtal = oversikt.getByTestId('statkort')
  await expect(huvudtal).toHaveCount(5)
  await expect(huvudtal.nth(0)).toHaveAttribute('data-matt', 'kolada:N03102')
  await expect(huvudtal.nth(1).getByRole('heading')).toHaveText('Nettokostnadsandel')
  await expect(huvudtal.nth(0).getByTestId('forklaring')).toContainText('blev kvar efter årets kostnader')
  // Senaste året, förändringen mot året före och källan.
  await expect(huvudtal.nth(0).getByTestId('statvarde')).toContainText('%')
  await expect(huvudtal.nth(0).getByTestId('statforandring')).toContainText(/procentenheter\s*mot \d{4}/)

  // Låneskulden per invånare beräknas av Kommunkollen och leder till lånekortet i varianten per invånare.
  const laneskuld = huvudtal.nth(4)
  await expect(laneskuld).toHaveAttribute('data-matt', 'kommunkollen:laneskuld-per-invanare')
  await expect(laneskuld.getByTestId('statvarde')).toContainText('kr/inv')
  await expect(laneskuld.getByTestId('kallrad')).toContainText('Beräknat av Kommunkollen')
  await laneskuld.getByRole('link', { name: 'Låneskuld per invånare' }).click()
  await expect(page).toHaveURL(/enhet=inv/)
  await expect(page).toHaveURL(/#kort-scb-BalansKnN-081$/)
  const kort = page.locator('[data-matt="scb:BalansKnN:081"]')
  await expect(kort).toHaveClass(/markerad/)
  await expect(kort).toBeInViewport()
  await expect(kort).toHaveAttribute('data-visad', 'kommunkollen:laneskuld-per-invanare')
  await expect(kort.getByTestId('kallrad')).toContainText('Beräknat av Kommunkollen')
})

test('grupperna är frågor med ingress', async ({ page }) => {
  await page.goto('/ekonomi')
  await expect(page.locator('#resultat').getByRole('heading', { name: 'Går kommunen med överskott?' })).toBeVisible()
  await expect(page.locator('#resultat .gruppingress')).toContainText('Årets resultat är skillnaden')
  await expect(page.getByRole('navigation', { name: 'Avsnitt' }).getByRole('link')).toHaveText([
    'Går kommunen med överskott?',
    'Var kommer pengarna ifrån?',
    'Vad kostar verksamheten och investeringarna?',
    'Hur mycket är lånat och vad är utlovat i pensioner?',
    'Klarar kommunen sina betalningar?',
  ])
})

test('ett kort växlar mellan totalt och per invånare med rätt källa, och valet speglas i URL:en', async ({ page }) => {
  await page.goto('/ekonomi')
  const kort = page.locator('[data-matt="scb:ResultKnN:040"]')
  const vaxel = kort.getByTestId('enhet')
  await expect(vaxel.getByRole('button', { name: 'Totalt (mnkr)' })).toHaveAttribute('aria-pressed', 'true')
  await expect(kort.getByTestId('kallrad')).toContainText('ResultKnN, post 040')

  await vaxel.getByRole('button', { name: 'Per invånare' }).click()
  await expect(page).toHaveURL(/enhet=inv/)
  await expect(kort.getByTestId('kallrad')).toContainText('Kolada')
  await expect(kort.getByTestId('kallrad')).toContainText('N03010')
  // Valet gäller alla kort med båda varianterna. Kort med bara en variant påverkas inte.
  await expect(page.locator('[data-matt="scb:BalansKnN:089"]')).toHaveAttribute('data-visad', 'kolada:N03046')
  await expect(page.locator('[data-matt="scb:BalansKnN:065"]').getByTestId('enhet')).toHaveCount(0)

  await kort.getByRole('button', { name: 'Tabell' }).click()
  await expect(kort.getByRole('table').getByRole('columnheader', { name: 'kr/inv' })).toBeVisible()

  await page.reload()
  await expect(kort.getByTestId('enhet').getByRole('button', { name: 'Per invånare' })).toHaveAttribute('aria-pressed', 'true')

  // CSV-exporten innehåller båda varianterna.
  const [nedladdning] = await Promise.all([page.waitForEvent('download'), kort.getByTestId('csv').click()])
  const text = await (await import('node:fs/promises')).readFile(await nedladdning.path(), 'utf-8')
  expect(text).toContain(';scb:ResultKnN:040;')
  expect(text).toContain(';kolada:N03010;')
})

test('översikten och växeln fungerar i mobilbredd', async ({ page }) => {
  await page.setViewportSize({ width: 375, height: 812 })
  await page.goto('/ekonomi')
  await expect(page.getByTestId('huvudtal').getByTestId('statkort')).toHaveCount(5)
  const kort = page.locator('[data-matt="scb:ResultKnN:030"]')
  await kort.getByTestId('enhet').getByRole('button', { name: 'Per invånare' }).click()
  await expect(kort).toHaveAttribute('data-visad', 'kolada:N03011')
  // Menyn ligger ovanför innehållet, och översikten och korten använder nästan hela bredden.
  for (const del of [page.getByTestId('huvudtal'), kort, page.locator('[data-matt="scb:BalansKnN:081"]')]) {
    const ruta = await del.boundingBox()
    expect(ruta!.x + ruta!.width).toBeLessThanOrEqual(375)
    expect(ruta!.width).toBeGreaterThan(300)
  }
})

// Brodiagram för resultatet och kopplingar mellan nyckeltal (#81)

test('brodiagrammet bygger upp årets resultat med källor och kontroll, och har tabellvy', async ({ page }) => {
  await page.goto('/ekonomi')
  const bro = page.getByTestId('resultatbro')
  await expect(bro.getByTestId('bro-ar')).toHaveValue('2025')
  await bro.getByTestId('bro-ar').selectOption('2024')
  await expect(page).toHaveURL(/bro=2024/)

  const steg = bro.getByTestId('brosteg')
  await expect(steg).toHaveCount(5)
  await expect(steg.nth(0)).toHaveAttribute('data-steg', 'skatteintakter')
  await expect(steg.nth(0).getByTestId('brovarde')).toHaveText('+1 355,3 mnkr')
  await expect(steg.nth(2).getByTestId('brovarde')).toHaveText('−2 017,7 mnkr')
  const finans = bro.locator('[data-steg="finansnetto"]')
  await expect(finans.getByTestId('brovarde')).toHaveText('−73,3 mnkr')
  await expect(finans.getByTestId('bromarkering')).toContainText('Summerat av Kommunkollen')
  await expect(steg.nth(4)).toHaveAttribute('data-steg', 'resultat')
  await expect(steg.nth(4).getByTestId('brovarde')).toHaveText('−91,0 mnkr')
  await expect(bro.getByTestId('brokontroll')).toContainText('summerar till årets resultat enligt SCB')
  await expect(bro.getByTestId('bro-budget')).toHaveAttribute('href', '/ekonomi/budget-och-utfall')
  await expect(bro.getByTestId('broavvikelse')).toHaveCount(0)
  await expect(bro.getByTestId('brotext')).toContainText('ger årets resultat −91,0 mnkr')
  await expect(bro.getByTestId('kallrad')).toContainText('SCB')

  // Tooltip med källa.
  await steg.nth(1).hover()
  await expect(bro.getByRole('tooltip')).toContainText('ResultKnN, post 050')

  await bro.getByRole('button', { name: 'Tabell' }).click()
  const tabell = bro.getByRole('table')
  await expect(tabell.getByRole('row')).toHaveCount(1 + 5)
  await expect(tabell.getByRole('row', { name: /Finansnetto/ })).toContainText('−73,3')
})

test('en länk under Hänger ihop med tar läsaren till kortet och markerar det', async ({ page }) => {
  await page.goto('/ekonomi')
  const sjalvfinansiering = page.locator('[data-matt="kolada:N03103"]')
  const samband = sjalvfinansiering.getByTestId('samband')
  await expect(samband.getByRole('heading', { name: 'Hänger ihop med' })).toBeVisible()
  const lan = samband.locator('li[data-till="scb:BalansKnN:081"]')
  await expect(lan).toContainText('Investeringar som inte självfinansieras kan betalas med lån.')
  await lan.getByRole('link').click()
  await expect(page).toHaveURL(/#kort-scb-BalansKnN-081$/)
  const kort = page.locator('[data-matt="scb:BalansKnN:081"]')
  await expect(kort).toHaveClass(/markerad/)
  await expect(kort).toBeInViewport()

  // Skatteintäkterna länkar till skatteunderlagsprognosen.
  await page.locator('[data-matt="scb:ResultKnN:040"]').getByTestId('samband').getByRole('link', { name: 'Skatteunderlagsprognos' }).click()
  await expect(page).toHaveURL(/\/ekonomi\/skatteunderlag$/)
})

// Genomsnittet för riket som jämförelselinje (#82)

test('ett kort visar Härnösand och riket för samma år, i diagram, tabell, huvudtal och CSV', async ({ page }) => {
  await page.goto('/ekonomi')
  const kort = page.locator('[data-matt="kolada:N03002"]')
  await expect(kort.getByTestId('riketstreck')).toHaveCount(0)

  await page.getByTestId('riket').click()
  await expect(page).toHaveURL(/riket=1/)
  await expect(page.getByTestId('riket')).toHaveAttribute('aria-pressed', 'true')
  // Ett streck per år, 2022–2025.
  await expect(kort.getByTestId('riketstreck')).toHaveCount(4)
  await expect(kort.getByTestId('riketforklaring')).toContainText('Riket')
  await kort.locator('rect.traffyta').last().hover()
  const tips = kort.getByTestId('riketstips')
  await expect(tips).toContainText('Riket: 30,0 %')
  await expect(tips).toContainText(/skillnad −\d+,\d procentenheter/)

  // Översiktens huvudtal: Riket: x, för samma år som Härnösand.
  const huvudtal = page.getByTestId('huvudtal').locator('[data-matt="kolada:N03002"]')
  await expect(huvudtal.getByTestId('statriket')).toContainText('Riket: 30,0 %')

  // Tabellen har riket och skillnaden.
  await kort.getByRole('button', { name: 'Tabell' }).click()
  const rad = kort.getByRole('row', { name: /2025/ })
  await expect(rad.getByTestId('riketcell')).toHaveText('30,0')
  await expect(rad).toContainText('procentenheter')

  // SCB-mått utan motsvarighet för riket förklarar varför ingen linje visas.
  await expect(page.locator('[data-matt="scb:BalansKnN:065"]').getByTestId('riket-saknas')).toContainText('inget genomsnitt för riket')
  const skatt = page.locator('[data-matt="scb:ResultKnN:040"]')
  await expect(skatt.getByTestId('riket-saknas')).toContainText('Riket finns per invånare')
  await skatt.getByRole('button', { name: 'Visa per invånare' }).click()
  await expect(page).toHaveURL(/enhet=inv/)
  await expect(skatt.getByTestId('riket-saknas')).toHaveCount(0)

  // CSV-exporten har med riket.
  const [nedladdning] = await Promise.all([page.waitForEvent('download'), kort.getByTestId('csv').click()])
  const text = await (await import('node:fs/promises')).readFile(await nedladdning.path(), 'utf-8')
  expect(text).toMatch(/;kolada:N03002;2025;[^\r\n]*;Härnösand\r\n/)
  expect(text).toMatch(/;kolada:N03002;2025;29,964932;[^\r\n]*;Riket\r\n/)

  // Av igen: inga streck.
  await page.getByTestId('riket').click()
  await expect(page).not.toHaveURL(/riket=1/)
  await expect(huvudtal.getByTestId('statriket')).toHaveCount(0)
})
