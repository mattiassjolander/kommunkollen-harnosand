import { expect, test } from '@playwright/test'
import { API_PORT } from '../playwright.config'

// Söm 2 (#48, #58): planförutsättningarna och budgetförslagen för 2027 är inlästa som utkast när
// servern startar (`--budgetforslag tests/fixtures/budgetforslag`). Utgivaren granskar och publicerar
// dem, och läsaren jämför förslagen mot planförutsättningarna och den antagna budgeten. En redaktör lägger
// till en åtgärd i Moderaternas förslag, och läsaren öppnar en nämnd och ser åtgärderna (#57).
// Förslagen hänvisar till behandlingen i fullmäktige 2026-06-15 § 108, och redaktören skriver
// Liberalernas summering med samma frågor som Moderaternas (#48). Protokollet 2026-06-15 ingår inte i
// e2e-urvalet, så hänvisningen visas utan yrkande; kopplingen till yrkandet prövas i söm 1.

test('läsaren jämför budgetförslagen mot planförutsättningarna', async ({ page }) => {
  // Redaktören lägger till en åtgärd för en ram som förslaget ändrar utan att ange åtgärder.
  await page.request.post('/api/auth/test/redaktor')
  await page.goto('/politik/budgetutkast')
  await expect(page.getByTestId('budgetutkast').or(page.getByTestId('inga-utkast')).first()).toBeVisible()
  const mUtkast = page.locator('[data-testid="budgetutkast"][data-nyckel="M"]')
  const rattad = (await mUtkast.count()) > 0
  if (rattad) {
    // Utgivaren ser åtgärderna med belopp, sida och täckning redan i utkastet.
    const ks = mUtkast.getByTestId('uppgifter')
    await expect(ks.getByTestId('atgard').first()).toContainText('Budgetminskning med 20 % Kommunstyrelseförvaltningen')
    await expect(ks.getByTestId('atgard').first().getByRole('link', { name: 's. 1' })).toHaveAttribute('href', /#page=1$/)
    await expect(ks.locator('tr', { hasText: 'Kommungemensam verksamhet' }).getByTestId('tackning')).toHaveText('Inga åtgärder anges')

    await mUtkast.getByRole('button', { name: 'Rätta' }).click()
    await mUtkast.locator('tr[data-ram="Kommungemensam verksamhet"]').getByTestId('lagg-till-atgard').click()
    const falt = mUtkast.locator('tr[data-ram-atgard="Kommungemensam verksamhet"]').last()
    await falt.getByRole('textbox', { name: 'Åtgärd', exact: true }).fill('Minskade kostnader för kommungemensam verksamhet')
    await falt.getByRole('textbox', { name: 'Åtgärdens belopp, mnkr' }).fill('-4')
    await falt.getByRole('textbox', { name: 'Åtgärdens sida' }).fill('1')
    await mUtkast.getByTestId('spara').click()
    await expect(mUtkast.getByRole('status')).toHaveText('Sparat som utkast.')
    await mUtkast.getByRole('button', { name: 'Avbryt' }).click()
    const kg = mUtkast.getByTestId('uppgifter').locator('tr', { has: page.getByRole('rowheader', { name: 'Kommungemensam verksamhet' }) })
    await expect(kg.getByTestId('tackning')).toHaveText('åtgärder för −4 mnkr')
  }

  // Redaktören skriver Liberalernas summering: samma frågor, ett svar per fråga.
  const lUtkast = page.locator('[data-testid="budgetutkast"][data-nyckel="L"]')
  const summerad = (await lUtkast.count()) > 0
  if (summerad) {
    await expect(lUtkast.getByTestId('behandling')).toContainText('KF 2026-06-15 § 108 (finns inte i plattformen)')
    await lUtkast.getByRole('button', { name: 'Rätta' }).click()
    const fragor = lUtkast.locator('.svar')
    await expect(fragor).toHaveCount(6)
    for (let i = 0; i < 6; i++) {
      const q = fragor.nth(i)
      if (i === 4) {
        await q.getByRole('checkbox', { name: 'Förslaget tar inte upp frågan' }).check()
      } else {
        await q.getByRole('textbox').first().fill('Besparingar om minst 30 mnkr i lägre kostnader läggs till resultatet.')
        await q.getByRole('textbox', { name: 'Sidor' }).fill('1')
      }
    }
    await lUtkast.getByTestId('spara').click()
    await expect(lUtkast.getByRole('status')).toHaveText('Sparat som utkast.')
    await lUtkast.getByRole('button', { name: 'Avbryt' }).click()
    await expect(lUtkast.getByTestId('summering')).toContainText('Analys')
    await expect(lUtkast.getByTestId('summering')).toContainText('Förslaget tar inte upp frågan')
  }

  // Utgivaren granskar och publicerar utkasten (de som inte redan publicerats i en tidigare körning).
  await page.request.post('/api/auth/test/utgivare')
  await page.goto('/politik')
  await page.getByRole('navigation', { name: 'Politik och beslut' }).getByRole('link', { name: 'Budgetutkast' }).click()
  await expect(page.getByTestId('budgetutkast').or(page.getByTestId('inga-utkast')).first()).toBeVisible()

  // Planförutsättningarna granskas med källa, sidlänk och kontrollsummor.
  const plan = page.locator('[data-testid="planutkast"][data-budgetar="2027"]')
  if ((await plan.count()) > 0) {
    const ks = plan.locator('[data-tabell="namnder"] tr', { hasText: 'Kommunstyrelsen' })
    await expect(ks).toContainText('187')
    await expect(ks.getByRole('link', { name: 'L s. 8' })).toHaveAttribute('href', /\/api\/budgetforslag\/\d+\/original#page=8$/)
    await expect(plan.locator('[data-tabell="namnder"]').getByTestId('kontroll')).toContainText('summa 2 144, angivet 2 145')
  }
  // Förslagets ram med förändringen mot planförutsättningarna och sidan i originalet.
  const l = page.locator('[data-testid="budgetutkast"][data-nyckel="L"]')
  if ((await l.count()) > 0) {
    const ks = l.getByTestId('uppgifter').locator('tr', { hasText: 'Kommunstyrelsen' })
    await expect(ks).toContainText('150 (−37)')
    await expect(ks.getByRole('link', { name: 's. 1' })).toHaveAttribute('href', /\/original#page=1$/)
    await expect(l.getByTestId('beraknat')).toContainText('60 mnkr · differens +20 mnkr')
  }
  for (const steg of ['granska', 'publicera'] as const) {
    while ((await page.getByTestId(steg).count()) > 0) {
      const antal = await page.getByTestId(steg).count()
      await page.getByTestId(steg).first().click()
      await expect(page.getByTestId(steg)).toHaveCount(antal - 1)
    }
  }
  await expect(page.getByTestId('inga-utkast')).toBeVisible()

  // Läsaren, utan inloggning.
  await page.request.post('/api/auth/logga-ut')
  await page.goto('/politik')
  await page.getByRole('navigation', { name: 'Politik och beslut' }).getByRole('link', { name: 'Budgetförslag' }).click()
  await expect(page).toHaveURL(/\/politik\/budget/)
  await expect(page.getByTestId('filter-budgetar')).toHaveValue('2027')

  const tabell = page.getByTestId('budgetjamforelse')
  const kolumner = tabell.locator('thead th[data-nyckel]')
  // Planförutsättningarna först, sedan den antagna budgeten och förslagen i alfabetisk ordning.
  await expect(tabell.getByTestId('plankolumn')).toBeVisible()
  await expect(kolumner).toHaveCount(4)
  await expect(kolumner.nth(0)).toHaveAttribute('data-nyckel', 'majoritet')
  await expect(kolumner.nth(0).getByTestId('antagen')).toHaveText('Antagen budget')
  await expect(kolumner.nth(1)).toHaveAttribute('data-nyckel', 'L')

  // Ram och förändring per nämnd. Cell 0 är planförutsättningen.
  const ks = tabell.locator('tr[data-organ="Kommunstyrelsen"] td')
  await expect(ks.nth(0)).toHaveText('187,0 mnkr')
  await expect(ks.nth(1)).toContainText('191,3 mnkr')
  await expect(ks.nth(2)).toContainText('150,0 mnkr')
  await expect(ks.nth(2).getByTestId('forandring')).toHaveText('−37,0 mnkr')
  await expect(ks.nth(2).getByTestId('differens')).toHaveText('mot antagen −41,3 mnkr (−21,6 %)')
  // Moderaterna angav bara förändringen; ramen räknas fram.
  await expect(ks.nth(3)).toContainText('150,0 mnkr')
  // Siffran länkar till sidan i originalet.
  await expect(ks.nth(1).getByRole('link')).toHaveAttribute('href', /\/api\/budgetforslag\/\d+\/original#page=4$/)

  // Skattesatsen: planförutsättningen ± förändringen.
  const skatt = tabell.locator('tr[data-rad="skattesats"] td')
  await expect(skatt.nth(0)).toHaveText('23,34 %')
  await expect(skatt.nth(3)).toContainText('23,24 %')
  await expect(skatt.nth(3)).toContainText('−10 öre')

  // Beräknat resultat och differens: L saknar finansiering för cirka 20 mnkr, SD cirka 22, M går ihop.
  const diff = tabell.getByTestId('resultatdifferens')
  await expect(diff.nth(1)).toHaveText('+20,0 mnkr')
  await expect(diff.nth(2)).toHaveText('−0,4 mnkr')
  await expect(diff.nth(3)).toHaveText('+23,1 mnkr')
  await expect(tabell.locator('tr[data-rad="beraknat"] td').nth(2)).toHaveText('60,0 mnkr')

  // Läsaren öppnar en nämnd och ser åtgärderna per förslag med belopp, sidlänk och täckning.
  const visa = tabell.locator('tr[data-organ="Kommunstyrelsen"]').getByTestId('visa-atgarder')
  await expect(visa).toHaveAttribute('aria-expanded', 'false')
  await visa.click()
  await expect(visa).toHaveAttribute('aria-expanded', 'true')
  const atg = tabell.locator('tr[data-atgarder="Kommunstyrelsen"] [data-testid="atgarder"]')
  await expect(atg).toHaveCount(4)
  await expect(atg.nth(2)).toContainText('Budgetminskning med 20 % Kommunstyrelseförvaltningen')
  await expect(atg.nth(2)).toContainText('−37,0 mnkr')
  await expect(atg.nth(2).getByRole('link', { name: 's. 1' })).toHaveAttribute('href', /\/api\/budgetforslag\/\d+\/original#page=1$/)
  await expect(atg.nth(2).getByTestId('tackning')).toHaveText('åtgärder för −37,0 av −37,0 mnkr')
  // Liberalerna ändrar ramen utan att ange åtgärder.
  await expect(atg.nth(1).getByTestId('tackning')).toHaveText('Inga åtgärder anges')
  if (rattad) {
    await tabell.locator('tr[data-organ="Kommungemensam verksamhet"]').getByTestId('visa-atgarder').click()
    await expect(tabell.locator('tr[data-atgarder="Kommungemensam verksamhet"] [data-testid="atgarder"]').nth(2))
      .toContainText('åtgärder för −4,0 av −4,0 mnkr')
  }
  // Socialnämnden: Moderaternas åtgärd har inget belopp.
  await tabell.locator('tr[data-organ="Socialnämnden"]').getByTestId('visa-atgarder').click()
  await expect(tabell.locator('tr[data-atgarder="Socialnämnden"] [data-testid="tackning"]').nth(2)).toHaveText('1 åtgärd utan belopp')
  await visa.click()
  await expect(tabell.locator('tr[data-atgarder="Kommunstyrelsen"]')).toHaveCount(0)

  // Behandlingen där förslagen ställdes. Protokollet är inte insamlat här, så hänvisningen står utan länk.
  const beh = tabell.locator('tr[data-rad="behandling"] [data-testid="behandling"]')
  await expect(beh).toHaveCount(4)
  await expect(beh.nth(2)).toContainText('KF 2026-06-15 § 108')
  await expect(beh.nth(2)).toContainText('Protokollet finns inte här än')

  // Summeringarna med samma frågor, märkta Analys, med sidlänkar.
  const sum = page.getByTestId('summering')
  await expect(sum.getByRole('heading')).toContainText('Analys')
  await expect(sum.locator('tbody tr')).toHaveCount(6)
  const inv = sum.locator('tr[data-fraga="investeringar"] td')
  const kolM = await sum.locator('thead th[data-nyckel]').evaluateAll((th) => th.findIndex((t) => t.getAttribute('data-nyckel') === 'M'))
  await expect(inv.nth(kolM)).toContainText('Investeringsnivån sänks med 16 mnkr')
  await expect(inv.nth(kolM).getByRole('link', { name: 's. 2' })).toHaveAttribute('href', /\/original#page=2$/)
  if (summerad) {
    const kolL = await sum.locator('thead th[data-nyckel]').evaluateAll((th) => th.findIndex((t) => t.getAttribute('data-nyckel') === 'L'))
    await expect(inv.nth(kolL)).toHaveText('Förslaget tar inte upp frågan')
  }

  // Resultat-, investerings-, balans- och kassaflödesbudget visas en gång för budgetåret.
  const pf = page.getByTestId('planforutsattningar')
  await expect(pf.locator('table')).toHaveCount(4)
  await expect(pf.locator('[data-tabell="investeringar"] tr', { hasText: 'Totalt' })).toContainText('147,0 mnkr')
  await expect(pf.locator('[data-tabell="kassaflode"] tr', { hasText: 'Totalt kassaflöde' })).toContainText('47,0 mnkr')
})

test('planförutsättningarna jämförs med SKR:s skatteunderlagsprognoser (#62)', async ({ page, request }) => {
  test.setTimeout(300_000) // LibreOffice räknar om prognosfilerna om de inte redan är insamlade
  const api = `http://127.0.0.1:${API_PORT}`
  expect((await request.post(`${api}/api/auth/test/redaktor`)).ok()).toBeTruthy()
  expect((await request.post(`${api}/api/insamlingar?kalla=skr-skatteunderlagsprognos`, { timeout: 300_000 })).ok()).toBeTruthy()

  // Planförutsättningarna publicerades i testet ovan.
  await page.goto('/politik/budget')
  const skr = page.getByTestId('skr-jamforelse')
  await expect(skr.getByRole('heading', { name: 'Jämfört med SKR:s prognoser' })).toBeVisible()
  // 1 483 + 734 mnkr.
  await expect(skr.getByTestId('skr-plan')).toContainText(/2\s217,0 mnkr/)

  const rader = skr.getByTestId('skr-tabell').locator('tbody tr')
  await expect(rader).toHaveCount(5)
  // Sorterade efter publiceringsdatum, senaste cirkuläret sist.
  await expect(rader.first()).toHaveAttribute('data-cirkular', '26:12')
  const c28 = skr.locator('tr[data-cirkular="26:28"]')
  await expect(c28).toContainText('6 okt 2026')
  await expect(c28).toContainText(/2\s222,1 mnkr/)
  await expect(c28).toContainText('+5,1 mnkr')
  await expect(c28).toContainText('+0,2 %')
  await expect(c28.getByRole('link', { name: '26:28' })).toHaveAttribute('href', /26028\.xlsm$/)
  await expect(skr.getByTestId('skr-forklaring')).toContainText('En differens behöver därför inte vara ett fel')
})
