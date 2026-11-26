import { expect, test, type Locator } from '@playwright/test'
import { API_PORT } from '../playwright.config'

// Märkningar (#162): chips på behandlingar och ärenden, och filter på märkning.
const api = `http://127.0.0.1:${API_PORT}`

test.beforeAll(async ({ request }) => {
  test.setTimeout(300_000) // insamlingen tolkar protokollen och bygger sökindexet
  expect((await request.post(`${api}/api/auth/test/redaktor`)).ok()).toBeTruthy()
  for (const kalla of ['harnosand-protokoll-ks', 'harnosand-protokoll-kf']) {
    expect((await request.post(`${api}/api/insamlingar?kalla=${kalla}`)).ok()).toBeTruthy()
  }
})

// Alla rader har märkningen. Listan kan uppdateras efter ett filter, så kontrollen görs om tills den håller.
async function allaHar(rader: Locator, markning: string) {
  await expect
    .poll(() =>
      rader.evaluateAll(
        (el, m) => el.length > 0 && el.every((e) => e.querySelector(`[data-markning="${m}"]`)),
        markning,
      ),
    )
    .toBe(true)
}

test('chips på sammanträdet, behandlingen och ärendet, och filter i behandlingslistan', async ({ page }) => {
  await page.goto('/politik?organ=KF')
  await page.locator('[data-testid="sammantrade"][data-datum="2026-02-23"]').getByRole('rowheader').getByRole('link').click()

  // KF 2026-02-23 § 5: votering 37–6 och reservation från SD.
  const rad = page.locator('[data-testid="behandling"][data-paragraf="5"]')
  const chips = rad.getByTestId('markning')
  await expect(chips.nth(0)).toHaveText('Votering 37–6')
  await expect(chips.nth(1)).toHaveText('Reservation SD')
  await expect(chips.nth(2)).toHaveText('Oenighet')
  // Votering, Reservation och Oenighet har en fylld ton, resten är konturchips. Texten står alltid där.
  await expect(chips.nth(0)).toHaveClass(/fylld/)
  const bakgrund = await chips.evaluateAll((el) => el.slice(0, 3).map((e) => getComputedStyle(e).backgroundColor))
  expect(new Set(bakgrund).size).toBe(3)
  // Ingen märkning "Enig".
  await expect(page.getByTestId('markning').filter({ hasText: /^Enig$/ })).toHaveCount(0)

  // Filtret på märkning visar bara behandlingar med märkningen och speglas i URL:en.
  const alla = await page.getByTestId('behandling').count()
  await page.getByTestId('markningsfilter').selectOption('votering')
  await expect(page).toHaveURL(/markning=votering/)
  await allaHar(page.getByTestId('behandling'), 'votering')
  expect(await page.getByTestId('behandling').count()).toBeLessThan(alla)
  await expect(page.getByTestId('antal-visade')).toContainText(`av ${alla} behandlingar`)
  await page.reload()
  await expect(page.getByTestId('markningsfilter')).toHaveValue('votering')
  await page.getByTestId('markningsfilter').selectOption('')
  await expect(page.getByTestId('behandling')).toHaveCount(alla)

  // Behandlingens sida och ärendets sida.
  await rad.locator('a.paragraf').click()
  await expect(page).toHaveURL(/\/paragraf\/5$/)
  await expect(page.getByTestId('markning').first()).toHaveText('Votering 37–6')
  await page.getByTestId('arendelank').click()
  await expect(page).toHaveURL(/\/politik\/arenden\/\d+$/)
  await expect(page.getByTestId('arendets-markningar').locator('[data-markning="votering"]')).toBeVisible()
  await expect(page.getByTestId('vag-behandling').locator('[data-markning="votering"]').first()).toBeVisible()
})

test('ledamotens röster har chips och filter', async ({ page, request }) => {
  const s = (await (await request.get(`${api}/api/sammantraden?organ=KF`)).json()).find(
    (x: { datum: string }) => x.datum === '2026-02-23',
  )
  const b = await (await request.get(`${api}/api/sammantraden/${s.id}/behandlingar/5`)).json()
  const molin = b.voteringar[0].roster.find((r: { namn: string }) => r.namn === 'Lennart Molin')
  await page.goto(`/politik/ledamoter/${molin.ledamot_id}`)
  const rost = page.locator('[data-testid="ledamotens-rost"][data-datum="2026-02-23"][data-paragraf="5"]')
  await expect(rost.locator('[data-markning="votering"]')).toHaveText('Votering 37–6')
  await page.getByTestId('ledamotens-roster').getByTestId('markningsfilter').selectOption('reservation')
  await expect(page).toHaveURL(/markning=reservation/)
  await allaHar(page.getByTestId('ledamotens-rost'), 'reservation')
})

test('sök: alla behandlingar med votering 2026, utan sökord', async ({ page }) => {
  await page.goto('/sok')
  await page.getByTestId('markningsfilter').selectOption('votering')
  await expect(page).toHaveURL(/markning=votering/)
  await page.getByTestId('filter-ar').selectOption('2026')
  await expect(page).toHaveURL(/ar=2026/)
  await expect(page.getByTestId('antal-traffar')).toContainText('med märkningen votering')
  await allaHar(page.getByTestId('traff'), 'votering')
  await expect(page.locator('[data-testid="traff"]:not([data-typ="behandling"]):not([data-typ="arende"])')).toHaveCount(0)

  // Med sökord och märkning.
  await page.getByTestId('sokfalt').fill('budget')
  await page.getByTestId('sokfalt').press('Enter')
  await expect(page).toHaveURL(/q=budget/)
  await expect(page.getByTestId('antal-traffar')).toContainText('för ”budget” med märkningen votering')
})

test('kommande ärenden: chips och filter på märkning', async ({ page, request }) => {
  const k = await (await request.get(`${api}/api/kommande`)).json()
  const m = k.markningar.find((x: { antal: number }) => x.antal > 0)
  test.skip(!m, 'inga märkningar bland de kommande ärendena')
  await page.goto('/politik/kommande')
  await expect(page.getByTestId('kommande-arende').first()).toBeVisible()
  // Raden är en knapp, så chipsen är inte länkar där (#174).
  await expect(page.getByTestId('kommande-arende').locator('a[data-testid="markning"]')).toHaveCount(0)
  await page.getByTestId('markningsfilter').selectOption(m.id)
  await expect(page).toHaveURL(new RegExp(`markning=${m.id}`))
  await expect(page.getByTestId('kommande-arende')).toHaveCount(m.antal)
  await allaHar(page.getByTestId('kommande-arende'), m.id)
})

// WCAG-kontrast mellan två färger som getComputedStyle ger dem, "rgb(r, g, b)".
function kontrast(a: string, b: string): number {
  const lum = (c: string) => {
    const [r, g, bl] = (c.match(/\d+(\.\d+)?/g) ?? []).slice(0, 3).map((x) => {
      const v = Number(x) / 255
      return v <= 0.04045 ? v / 12.92 : ((v + 0.055) / 1.055) ** 2.4
    })
    return 0.2126 * r + 0.7152 * g + 0.0722 * bl
  }
  const [hi, lo] = [lum(a), lum(b)].sort((x, y) => y - x)
  return (hi + 0.05) / (lo + 0.05)
}

test('färgade chips med kontrast i ljust och mörkt läge, och chippet länkar till Sök (#174)', async ({ page }) => {
  for (const colorScheme of ['light', 'dark'] as const) {
    await page.emulateMedia({ colorScheme })
    await page.goto('/politik?organ=KF')
    await page.locator('[data-testid="sammantrade"][data-datum="2026-02-23"]').getByRole('rowheader').getByRole('link').click()
    const chips = page.locator('[data-testid="behandling"][data-paragraf="5"]').getByTestId('markning')
    await expect(chips.nth(2)).toHaveText('Oenighet')
    const farger = await chips.evaluateAll((el) =>
      el.slice(0, 3).map((e) => ({ fg: getComputedStyle(e).color, bg: getComputedStyle(e).backgroundColor })),
    )
    // Tre olika fyllningar och tre olika textfärger, och texten klarar 4,5:1 mot fyllningen.
    expect(new Set(farger.map((f) => f.bg)).size).toBe(3)
    expect(new Set(farger.map((f) => f.fg)).size).toBe(3)
    for (const f of farger) expect(kontrast(f.fg, f.bg), `${colorScheme}: ${f.fg} på ${f.bg}`).toBeGreaterThanOrEqual(4.5)
  }

  // Ett konturchip har texten i --ink.
  const ink = await page.evaluate(() => {
    const p = document.createElement('p')
    p.style.color = 'var(--ink)'
    document.body.append(p)
    return getComputedStyle(p).color
  })
  const kontur = page.locator('[data-testid="markning"].kontur').first()
  if (await kontur.count()) await expect(kontur).toHaveCSS('color', ink)

  // Klick på chippet öppnar Sök med märkningen förvald och listar alla träffar med den.
  const votering = page.locator('[data-testid="behandling"][data-paragraf="5"]').locator('[data-markning="votering"]')
  await votering.focus()
  await expect(votering).toBeFocused()
  await votering.click()
  await expect(page).toHaveURL(/\/sok\?markning=votering$/)
  await expect(page.getByTestId('markningsfilter')).toHaveValue('votering')
  await expect(page.getByTestId('antal-traffar')).toContainText('med märkningen votering')
  await allaHar(page.getByTestId('traff'), 'votering')
})

test('sök: hjälptext om märkningen och filtren på samma linje (#174)', async ({ page }) => {
  await page.goto('/sok')
  await expect(page.getByTestId('markningshjalp')).toHaveText('Välj en märkning och lämna sökrutan tom för att se alla.')
  const kontroller = page.getByTestId('filterrad').locator('select')
  await expect(kontroller).toHaveCount(4)
  const lagen = await kontroller.evaluateAll((el) =>
    el.map((e) => {
      const r = e.getBoundingClientRect()
      return { top: Math.round(r.top), hojd: Math.round(r.height) }
    }),
  )
  expect(new Set(lagen.map((l) => l.top)).size, JSON.stringify(lagen)).toBe(1)
  expect(new Set(lagen.map((l) => l.hojd)).size, JSON.stringify(lagen)).toBe(1)
  const etiketter = await page
    .getByTestId('filterrad')
    .locator('label')
    .evaluateAll((el) => el.map((e) => `${getComputedStyle(e).fontSize} ${getComputedStyle(e).color}`))
  expect(new Set(etiketter).size).toBe(1)

  // Med sökord försvinner hjälptexten.
  await page.getByTestId('sokfalt').fill('budget')
  await page.getByTestId('sokfalt').press('Enter')
  await expect(page.getByTestId('markningshjalp')).toHaveCount(0)
})
