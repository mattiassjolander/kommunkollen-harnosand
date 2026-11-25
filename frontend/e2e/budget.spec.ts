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
  await page.goto('/redaktion/budgetutkast')
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
  await page.getByRole('navigation', { name: 'Huvudvyer' }).getByRole('link', { name: 'Redaktion' }).click()
  await page.getByRole('navigation', { name: 'Huvudvyer' }).getByRole('link', { name: 'Budgetutkast' }).click()
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
  await page.getByRole('navigation', { name: 'Huvudvyer' }).getByRole('link', { name: 'Budgetförslag' }).click()
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
  await expect(atg.nth(2).getByTestId('atgardsgrupp')).toHaveText(['Besparingar'])
  await expect(atg.nth(2)).toContainText('Budgetminskning med 20 % Kommunstyrelseförvaltningen')
  await expect(atg.nth(2)).toContainText('−37,0 mnkr')
  await expect(atg.nth(2).getByRole('link', { name: 's. 1' })).toHaveAttribute('href', /\/api\/budgetforslag\/\d+\/original#page=1$/)
  await expect(atg.nth(2).getByTestId('tackning')).toHaveText('åtgärder för −37,0 av −37,0 mnkr')
  // Liberalernas åtgärder är inte avlästa, och det står i stället för att ramen saknar åtgärder.
  await expect(atg.nth(1).getByTestId('atgardsstatus')).toHaveText('Åtgärderna är inte avlästa')
  await expect(atg.nth(1).getByTestId('tackning')).toHaveCount(0)
  if (rattad) {
    await tabell.locator('tr[data-organ="Kommungemensam verksamhet"]').getByTestId('visa-atgarder').click()
    await expect(tabell.locator('tr[data-atgarder="Kommungemensam verksamhet"] [data-testid="atgarder"]').nth(2))
      .toContainText('åtgärder för −4,0 av −4,0 mnkr')
  }
  // Socialnämnden: Moderaternas åtgärd har inget belopp.
  await tabell.locator('tr[data-organ="Socialnämnden"]').getByTestId('visa-atgarder').click()
  const soc = tabell.locator('tr[data-atgarder="Socialnämnden"] [data-testid="atgarder"]').nth(2)
  await expect(soc.getByTestId('atgardsgrupp')).toHaveText(['Utan belopp'])
  await expect(soc.getByTestId('tackning')).toHaveText('1 åtgärd utan belopp')
  await visa.click()
  await expect(tabell.locator('tr[data-atgarder="Kommunstyrelsen"]')).toHaveCount(0)

  // Alla nämnder kan öppnas på en gång. Moderaterna ändrar inte Kommunfullmäktiges ram och anger inga
  // åtgärder för den, och SD tar upp alla nämnder men har inga avlästa åtgärder.
  await page.getByTestId('visa-alla-atgarder').click()
  await expect(tabell.locator('tr.atgarder')).toHaveCount(await tabell.locator('tr[data-organ]').count())
  const kf = tabell.locator('tr[data-atgarder="Kommunfullmäktige"] [data-testid="atgarder"]')
  await expect(kf.nth(2).getByTestId('atgardsstatus')).toHaveText('Inga besparingar eller satsningar anges')
  await expect(kf.nth(3).getByTestId('atgardsstatus')).toHaveText('Åtgärderna är inte avlästa')
  await page.getByTestId('visa-alla-atgarder').click()
  await expect(tabell.locator('tr.atgarder')).toHaveCount(0)

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

// Ett budgetförslag för sig (#147): läsaren öppnar Moderaternas förslag från jämförelsen och ser nyckeltalen,
// summeringen och graferna mot planförutsättningarna. Förslagen publicerades i det första testet.
test('läsaren öppnar ett budgetförslag och ser graferna mot planförutsättningarna (#147)', async ({ page }) => {
  await page.request.post('/api/auth/logga-ut')
  await page.goto('/politik/budget')
  await page.getByTestId('budgetjamforelse').locator('thead th[data-nyckel="M"]').getByTestId('forslagslank').click()
  await expect(page).toHaveURL(/\/politik\/budget\/2027\/M$/)
  await expect(page.getByRole('heading', { level: 1 })).toHaveText('Moderaternas budgetförslag för Härnösands kommun 2027')
  await expect(page.getByTestId('brodsmula')).toContainText('Budgetförslag')
  await expect(page.getByTestId('originalet')).toHaveAttribute('href', /\/api\/budgetforslag\/\d+\/original$/)

  // Nyckeltalen: −37 − 4 + 0 + 1 + 15 + 13 = −12 mnkr, och skatten sänks med 10 öre.
  const nyckeltal = page.getByTestId('nyckeltal')
  await expect(nyckeltal.locator('[data-nyckeltal="forandring"]')).toContainText('−12,0 mnkr')
  await expect(nyckeltal.locator('[data-nyckeltal="skattesats"]')).toContainText('−10 öre')
  await expect(nyckeltal.locator('[data-nyckeltal="resultat"]')).toContainText('2,5 % av skatter och bidrag')
  await expect(nyckeltal.locator('[data-nyckeltal="differens"]')).toContainText('beräknat resultat')
  // Redaktionens summering, märkt Analys och med sidhänvisningar.
  const summering = page.getByTestId('summering')
  await expect(summering.getByRole('heading')).toContainText('Analys')
  await expect(summering.locator('[data-fraga="besparingar"]')).toContainText('Budgetminskning med 20 %')
  await expect(summering.locator('[data-fraga="besparingar"]').getByRole('link', { name: 's. 1' })).toHaveAttribute('href', /#page=1$/)

  // A: från största ökning till största minskning, med ett streck för den antagna budgetens förändring.
  const a = page.getByTestId('graf-forandring')
  const staplar = a.getByTestId('forandringsstapel')
  await expect(staplar.first()).toHaveAttribute('data-organ', 'Skolnämnden')
  await expect(staplar.first().getByTestId('forandringsvarde')).toHaveText('+15,0 mnkr')
  await expect(a.locator('[data-organ="Kommunstyrelsen"]').getByTestId('forandringsvarde')).toHaveText('−37,0 mnkr')
  await expect(a.getByTestId('antagenstreck').first()).toBeAttached()
  await expect(a.getByRole('list', { name: /Förändring mot planförutsättningarna/ })).toBeVisible()
  // Tabellvyn för skärmläsare och utskrift.
  await a.getByRole('button', { name: 'Tabell' }).click()
  await expect(a.getByTestId('tabell-forandring').locator('tr', { hasText: 'Kommunstyrelsen' })).toContainText('−37,0 mnkr')
  await expect(a.getByTestId('tabell-forandring').getByRole('columnheader', { name: 'Antagen budget' })).toBeVisible()

  // B: planförutsättningarnas resultat, ramförändringarna i samma ordning som A, skatten, det beräknade resultatet,
  // det som inte redovisas och sist det budgeterade resultatet.
  const b = page.getByTestId('graf-resultat')
  const steg = b.getByTestId('brosteg')
  const ordning = await steg.evaluateAll((s) => s.map((x) => x.getAttribute('data-steg')))
  expect(ordning).toEqual([
    'plan',
    'ram-Skolnämnden',
    'ram-Socialnämnden',
    'ram-Samhällsnämnden',
    'ram-Kommunfullmäktige',
    'ram-Kommungemensam verksamhet',
    'ram-Kommunstyrelsen',
    'skatt',
    'beraknat',
    'ej-redovisat',
    'budgeterat',
  ])
  // En högre ram ger ett lägre resultat.
  await expect(b.locator('[data-steg="ram-Skolnämnden"]').getByTestId('brovarde')).toHaveText('−15,0 mnkr')
  await expect(b.locator('[data-steg="ram-Kommunstyrelsen"]').getByTestId('brovarde')).toHaveText('+37,0 mnkr')
  await expect(b.locator('[data-steg="ej-redovisat"]')).toContainText('Ej redovisat')
  await expect(b.getByTestId('brotext')).toContainText('ger det beräknade resultatet')
  // Stående kolumner på bred skärm, en rad per steg på smal.
  const y = async () => Promise.all([steg.nth(0), steg.nth(1)].map(async (s) => (await s.boundingBox())!.y))
  const [y0, y1] = await y()
  expect(Math.abs(y0 - y1)).toBeLessThan(2)
  await page.setViewportSize({ width: 390, height: 844 })
  const [m0, m1] = await y()
  expect(m1).toBeGreaterThan(m0 + 10)
  await page.setViewportSize({ width: 1280, height: 720 })

  // D: åtgärderna per nämnd efter förändringens storlek, med täckning.
  const d = page.getByTestId('atgarder-per-namnd')
  await expect(d.getByTestId('namndatgarder').first()).toHaveAttribute('data-organ', 'Kommunstyrelsen')
  const ks = d.locator('[data-organ="Kommunstyrelsen"]')
  await expect(ks.getByTestId('atgard')).toContainText('Budgetminskning med 20 % Kommunstyrelseförvaltningen')
  await expect(ks.getByTestId('atgard').getByRole('link', { name: 's. 1' })).toHaveAttribute('href', /#page=1$/)
  await expect(ks.getByTestId('tackning')).toHaveText('åtgärderna förklarar −37,0 av −37,0 mnkr')
  await expect(d.locator('[data-organ="Socialnämnden"]').getByTestId('tackning')).toHaveText('inga belopp angivna')
  await expect(d.locator('[data-organ="Kommunfullmäktige"]').getByTestId('tackning')).toHaveText('Inga åtgärder anges')

  // Byta förslag: de andra förslagen för året och länken till jämförelsen.
  const byt = page.getByTestId('byt-forslag')
  await expect(byt.locator('[data-nyckel="M"]')).toHaveCount(0)
  await byt.locator('[data-nyckel="L"]').click()
  await expect(page).toHaveURL(/\/politik\/budget\/2027\/L$/)
  await expect(page.getByRole('heading', { level: 1 })).toHaveText('Liberalernas budgetförslag 2027')

  // Den antagna budgeten har en egen sida, utan streck för sig själv.
  await page.getByTestId('byt-forslag').getByRole('link', { name: /Antagen budget/ }).click()
  await expect(page.getByTestId('antagen')).toHaveText('Antagen budget')
  // Vyvalet följer med när läsaren byter förslag, och tabellen valdes ovan.
  await page.getByTestId('graf-forandring').getByRole('button', { name: 'Diagram' }).click()
  await expect(page.getByTestId('graf-forandring').getByTestId('forandringsstapel').first()).toBeVisible()
  await expect(page.getByTestId('antagenstreck')).toHaveCount(0)
  await page.getByTestId('graf-forandring').getByRole('button', { name: 'Tabell' }).click()
  await expect(page.getByTestId('tabell-forandring').getByRole('columnheader', { name: 'Antagen budget' })).toHaveCount(0)

  await page.getByTestId('alla-budgetforslag').click()
  await expect(page).toHaveURL(/\/politik\/budget\?ar=2027$/)

  // Ett förslag som inte är publicerat finns inte för läsaren.
  await page.goto('/politik/budget/2027/KD')
  await expect(page.getByRole('heading', { level: 1 })).toHaveText('Sidan finns inte')
  await expect(page.getByTestId('graf-forandring')).toHaveCount(0)
})

// En nämnd som förslaget inte anger visas som "Anges inte", aldrig som noll, och räknas inte i brodiagrammet (#147).
// Inget förslag i testdatan utelämnar en nämnd, så svaret ändras på vägen.
test('en nämnd som förslaget inte anger visas som Anges inte (#147)', async ({ page }) => {
  await page.route('**/api/budget/2027', async (route) => {
    const svar = await route.fetch()
    const j = await svar.json()
    const l = j.forslag.find((f: { nyckel: string }) => f.nyckel === 'L')
    const utan = (r: { organ: string }) => r.organ !== 'Samhällsnämnden'
    l.uppgifter.ramar = l.uppgifter.ramar.filter(utan)
    l.berakning.ramar = l.berakning.ramar.filter(utan)
    await route.fulfill({ response: svar, json: j })
  })
  await page.goto('/politik/budget/2027/L')
  const rad = page.getByTestId('graf-forandring').locator('[data-organ="Samhällsnämnden"]')
  await expect(rad.getByTestId('anges-inte')).toHaveText('Anges inte')
  await expect(rad.getByTestId('forandringsvarde')).toHaveCount(0)
  await expect(page.getByTestId('graf-forandring').getByTestId('forandringsstapel').last()).toHaveAttribute('data-organ', 'Samhällsnämnden')
  await expect(page.getByTestId('graf-resultat').locator('[data-steg="ram-Samhällsnämnden"]')).toHaveCount(0)
  await expect(page.getByTestId('graf-resultat').locator('[data-steg="ram-Skolnämnden"]')).toHaveCount(1)
  await expect(page.getByTestId('atgarder-per-namnd').locator('[data-organ="Samhällsnämnden"]').getByTestId('tackning')).toHaveText('Anges inte')
})

// Söm 1 (#76): en utgivare återkallar planförutsättningarna för 2027 och Sverigedemokraternas förslag. Läsaren ser
// förslagen utan förändringar och notiser i stället för det återkallade. Testet körs sist i filen, eftersom de
// återkallade uppgifterna inte kommer tillbaka förrän en rättad version läses in och publiceras.
test('utgivaren återkallar planförutsättningarna och ett förslag (#76)', async ({ page }) => {
  const motivering = 'Kommunstyrelsens ram är fel avläst. Påpekat av en läsare 2026-11-20.'
  const planPubl = page.locator('[data-testid="publicerad"][data-slag="planforutsattningar"][data-budgetar="2027"]')
  const sdPubl = page.locator('[data-testid="publicerad"][data-nyckel="SD"]')
  const laddad = () => expect(page.getByTestId('publicerad').or(page.getByTestId('aterkallad')).first()).toBeVisible()

  // En redaktör kan inte återkalla.
  await page.request.post('/api/auth/test/redaktor')
  await page.goto('/redaktion/budgetutkast')
  await laddad()
  await expect(page.getByTestId('aterkalla')).toHaveCount(0)

  await page.request.post('/api/auth/test/utgivare')
  await page.goto('/redaktion/budgetutkast')
  await laddad()
  for (const publ of [planPubl, sdPubl]) {
    if ((await publ.count()) === 0) continue // återkallad i en tidigare körning
    await publ.getByTestId('aterkalla').click()
    await expect(publ.getByTestId('spara-aterkallelse')).toBeDisabled()
    await publ.getByTestId('aterkalla-motivering').fill(motivering)
    await publ.getByTestId('spara-aterkallelse').click()
    await expect(publ).toHaveCount(0)
  }
  const planAter = page.locator('[data-testid="aterkallad"][data-budgetar="2027"]:not([data-nyckel])')
  await expect(planAter.getByTestId('aterkallelse')).toHaveText(motivering)
  await expect(planAter).toContainText('test-utgivare@kommunkollen.test')
  await expect(page.locator('[data-testid="aterkallad"][data-nyckel="SD"]').getByTestId('aterkallelse')).toHaveText(motivering)

  // Läsaren ser året utan planförutsättningar och utan Sverigedemokraternas förslag, med notiser.
  await page.request.post('/api/auth/logga-ut')
  await page.goto('/politik/budget')
  await expect(page.getByTestId('aterkallat-planforutsattningar')).toContainText(
    'Planförutsättningarna för 2027 är tillbakadragna för rättning.',
  )
  await expect(page.locator('[data-testid="aterkallat-forslag"][data-nyckel="SD"]')).toHaveText(
    'Förslaget från SD är tillbakadraget för rättning.',
  )
  const tabell = page.getByTestId('budgetjamforelse')
  await expect(tabell.locator('thead th[data-nyckel]')).toHaveCount(3)
  await expect(tabell.locator('thead th[data-nyckel="SD"]')).toHaveCount(0)
  await expect(tabell.getByTestId('plankolumn')).toHaveCount(0)
  await expect(tabell.getByTestId('forandring')).toHaveCount(0)
  await expect(tabell.getByTestId('resultatdifferens')).toHaveCount(0)
  await expect(page.getByTestId('planforutsattningar')).toHaveCount(0)
  // Ramarna står kvar som förslagen anger dem.
  await expect(tabell.locator('tr[data-organ="Kommunstyrelsen"] td').nth(1)).toContainText('150,0 mnkr')

  // Det återkallade förslagets egen sida visar samma notis och inga grafer (#147).
  await page.goto('/politik/budget/2027/SD')
  await expect(page.getByRole('heading', { level: 1 })).toHaveText('Sverigedemokraternas budgetförslag 2027')
  await expect(page.getByTestId('aterkallat-forslag')).toHaveText('Förslaget från SD är tillbakadraget för rättning.')
  await expect(page.getByTestId('graf-forandring')).toHaveCount(0)
  await expect(page.getByTestId('graf-resultat')).toHaveCount(0)
  await expect(page.getByTestId('atgarder-per-namnd')).toHaveCount(0)
  await expect(page.getByTestId('byt-forslag').getByTestId('alla-budgetforslag')).toHaveText('Alla budgetförslag 2027')
})

// Söm 2 (#76, del 2): redaktören skapar nya versioner av de återkallade uppgifterna och rättar dem i gränssnittet,
// utgivaren granskar och publicerar, och läsaren ser markeringen Ändrad efter publicering och den förra versionen.
// Bygger på testet ovan. Rättningarna ändrar inga belopp, så att jämförelsen i det första testet står sig.
test('återkallade uppgifter rättas i en ny version och publiceras igen (#76)', async ({ page }) => {
  const andring = 'Anmärkningen om finansieringen saknades. Påpekat av en läsare 2026-11-21.'
  const planandring = 'Källan för Kommunstyrelsen var fel angiven.'
  await page.request.post('/api/auth/test/redaktor')
  await page.goto('/redaktion/budgetutkast')
  await expect(page.getByTestId('aterkallad').first()).toBeVisible()

  // Förslaget: en ny version från den återkallade, med motivering. Utkastet öppnas för rättning.
  const sdAter = page.locator('[data-testid="aterkallad"][data-nyckel="SD"]').first()
  await sdAter.getByTestId('ny-version').click()
  await expect(sdAter.getByTestId('spara-ny-version')).toBeDisabled()
  await sdAter.getByTestId('ny-version-motivering').fill(andring)
  await sdAter.getByTestId('spara-ny-version').click()
  const sd = page.locator('[data-testid="budgetutkast"][data-nyckel="SD"]')
  await expect(sd.getByTestId('utkast-andring')).toContainText(andring)
  await sd.getByRole('textbox', { name: 'Anmärkning' }).fill('Rättad efter påpekande.')
  await sd.getByTestId('spara').click()
  await expect(sd.getByRole('status')).toHaveText('Sparat som utkast.')

  // Planförutsättningarna rättas här, inte bara i Excelfilen.
  const planAter = page.locator('[data-testid="aterkallad"][data-budgetar="2027"]:not([data-nyckel])').first()
  await planAter.getByTestId('ny-version').click()
  await planAter.getByTestId('ny-version-motivering').fill(planandring)
  await planAter.getByTestId('spara-ny-version').click()
  const plan = page.locator('[data-testid="planutkast"][data-budgetar="2027"]')
  const form = plan.getByTestId('planformular')
  await form.locator('[data-tabell="namnder"] tr[data-post="Kommunstyrelsen"]').getByRole('textbox', { name: 'Källa' }).fill('L s. 8, M s. 1')
  await form.getByTestId('spara-plan').click()
  await expect(plan.getByRole('status')).toHaveText('Sparat som utkast.')
  await expect(plan.locator('[data-tabell="namnder"] tr', { hasText: 'Kommunstyrelsen' })).toContainText('L s. 8, M s. 1')

  // Utgivaren granskar och publicerar.
  await page.request.post('/api/auth/test/utgivare')
  await page.goto('/redaktion/budgetutkast')
  await expect(page.getByTestId('budgetutkast').first()).toBeVisible()
  for (const steg of ['granska', 'publicera'] as const) {
    while ((await page.getByTestId(steg).count()) > 0) {
      const antal = await page.getByTestId(steg).count()
      await page.getByTestId(steg).first().click()
      await expect(page.getByTestId(steg)).toHaveCount(antal - 1)
    }
  }
  await expect(page.getByTestId('inga-utkast')).toBeVisible()

  // Läsaren ser förslaget och planförutsättningarna igen, märkta Ändrad efter publicering.
  await page.request.post('/api/auth/logga-ut')
  await page.goto('/politik/budget')
  const tabell = page.getByTestId('budgetjamforelse')
  await expect(tabell.locator('thead th[data-nyckel]')).toHaveCount(4)
  await expect(page.getByTestId('aterkallat-forslag')).toHaveCount(0)
  await expect(page.getByTestId('aterkallat-planforutsattningar')).toHaveCount(0)
  await expect(tabell.locator('thead th[data-nyckel="SD"]').getByTestId('andrad-efter-publicering')).toHaveText('Ändrad efter publicering')
  await expect(page.getByTestId('plan-andrad')).toContainText(planandring)
  const sdAndring = page.locator('[data-testid="andringar"] li[data-nyckel="SD"]')
  await expect(sdAndring).toContainText(andring)

  // Den förra versionen går att öppna.
  await sdAndring.getByTestId('forra-versionen').click()
  await expect(page).toHaveURL(/\/politik\/budget\/tidigare\/forslag\/\d+$/)
  await expect(page.getByTestId('tidigare-notis')).toContainText('Den drogs tillbaka för rättning och har ersatts av en rättad version.')
  await expect(page.getByTestId('tidigare-ramar')).toContainText('Kommunstyrelsen')
  await page.getByRole('link', { name: 'Till den gällande versionen' }).click()
  await expect(page).toHaveURL(/\/politik\/budget\?ar=2027$/)
  await page.getByTestId('plan-andrad').getByTestId('forra-versionen').click()
  await expect(page.getByTestId('tidigare-version').locator('[data-tabell="namnder"] tr', { hasText: 'Kommunstyrelsen' })).toContainText('L s. 8')
})

// Budget jämfört med utfall (#83): uppföljningen för 2027 läses in som utkast med förslagen. Utgivaren
// kontrollerar den räknade avvikelsen mot dokumentets och publicerar, och läsaren ser antagen och reviderad
// budget, prognos och utfall per nämnd under Ekonomi, med sidlänkar och den antagna budgeten ur årsplanen.
test('läsaren jämför budget och utfall per nämnd (#83)', async ({ page }) => {
  await page.request.post('/api/auth/test/utgivare')
  await page.goto('/redaktion/budgetutkast')
  await expect(page.getByTestId('budgetutkast').or(page.getByTestId('inga-utkast')).first()).toBeVisible()
  const utkast = page.locator('[data-testid="uppfoljningsutkast"][data-budgetar="2027"]')
  if ((await utkast.count()) > 0) {
    const soc = utkast.locator('tr[data-organ="Socialnämnden"]')
    await expect(soc.getByTestId('uppfoljning-raknad')).toHaveText('-10,2')
    await expect(soc.getByRole('link', { name: '905,2' })).toHaveAttribute('href', /arsredovisning-2027\.pdf#page=81$/)
    await utkast.getByTestId('granska-uppfoljning').click()
    await utkast.getByTestId('publicera-uppfoljning').click()
    await expect(utkast).toHaveCount(0)
  }

  // Läsaren hittar fliken under Ekonomi. Brodiagrammets länk prövas i ekonomi.spec.ts.
  await page.request.post('/api/auth/logga-ut')
  await page.goto('/ekonomi')
  await page.getByRole('navigation', { name: 'Huvudvyer' }).getByRole('link', { name: 'Budget och utfall' }).click()
  await expect(page).toHaveURL(/\/ekonomi\/budget-och-utfall/)
  await expect(page.getByTestId('uppfoljning-ar')).toHaveValue('2027')

  const soc = page.getByTestId('namndtabell').locator('tr[data-organ="Socialnämnden"]')
  await expect(soc).toContainText('893,1 mnkr')
  await expect(soc).toContainText('905,2 mnkr')
  await expect(soc).toContainText('915,4 mnkr')
  await expect(soc.locator('[data-kolumn="avvikelse"]')).toContainText('−10,2 mnkr')
  await expect(soc.locator('[data-kolumn="avvikelse-antagen"]')).toContainText('mot antagen −22,3 mnkr')
  await expect(soc.locator('[data-kolumn="prognos"]')).toContainText('−12,5 mnkr')
  // Den antagna ramen länkar till sidan i årsplanen, utfallet till sidan i årsredovisningen.
  await expect(soc.getByRole('link', { name: '893,1 mnkr' })).toHaveAttribute('href', /\/api\/budgetforslag\/\d+\/original#page=4$/)
  await expect(soc.getByRole('link', { name: '915,4 mnkr' })).toHaveAttribute('href', /#page=81$/)
  await expect(page.getByTestId('uppfoljning-kontroll')).toBeVisible()
  await expect(page.getByTestId('utan-uppfoljning')).toContainText('Kommungemensam verksamhet')
  await expect(page.getByTestId('avvikelse-resultat')).toHaveText('−12,2 mnkr')
  await expect(page.getByTestId('uppfoljning-kallor')).toContainText('antagen av KF')

  // Diagrammen ovanför tabellerna. Resultatet: antagen, reviderad, prognos och utfall, och den antagna budgeten
  // som streckad linje.
  const resultat = page.getByTestId('resultatdiagram')
  await expect(resultat.getByTestId('resultatstapel')).toHaveCount(4)
  await expect(resultat.getByTestId('resultatvarde')).toHaveText(['51,0 mnkr', '50,3 mnkr', '31,0 mnkr', '38,1 mnkr'])
  await expect(resultat.getByTestId('referenslinje')).toBeVisible()
  await resultat.locator('[data-stapel="utfall"]').hover()
  await expect(resultat.getByRole('tooltip')).toContainText('Årsredovisning 2027, s. 46')

  // Nämnderna sorteras efter avvikelsen. Arbetslivsnämnden har reviderad budget 0 och utelämnas med en mening.
  const avvikelse = page.getByTestId('avvikelsediagram')
  const staplar = avvikelse.getByTestId('avvikelsestapel')
  await expect(staplar).toHaveCount(6)
  await expect(staplar.first()).toHaveAttribute('data-organ', 'Kommunövergripande verksamhet')
  await expect(staplar.last()).toHaveAttribute('data-organ', 'Socialnämnden')
  await expect(avvikelse.locator('[data-organ="Arbetslivsnämnden"]')).toHaveCount(0)
  await expect(page.getByTestId('nollbudget')).toContainText('Arbetslivsnämnden visas inte i diagrammet')
  await expect(page.getByTestId('namndtabell').locator('tr[data-organ="Arbetslivsnämnden"]')).toBeVisible()
  // Prognosstreck för de fem nämnder som har en prognos.
  await expect(avvikelse.getByTestId('prognosstreck')).toHaveCount(5)
  const socStapel = avvikelse.locator('[data-organ="Socialnämnden"]')
  await expect(socStapel.getByTestId('avvikelsevarde')).toHaveText('−10,2 mnkr')
  await socStapel.hover()
  const tips = avvikelse.getByRole('tooltip')
  await expect(tips).toContainText('−10,2 mnkr (−1 %) mot reviderad budget')
  await expect(tips).toContainText('−22,3 mnkr mot antagen budget')
  await expect(tips).toContainText('−12,5 mnkr enligt prognosen i delårsrapporten')
  await expect(tips).toContainText('Årsredovisning 2027, s. 81')
  await expect(tips).toContainText('Delårsrapport augusti 2027, s. 25')

  // #134: ändringarna av budgeten under året, kopplade till beslutet. Socialnämndens och skolnämndens ändring
  // hänvisar till KF 2026-06-15 § 108. Protokollet ingår inte i e2e-urvalet, så beslutet visas som hänvisning;
  // länken till behandlingen prövas i söm 1. Kommunstyrelsens belopp står inte i beslutet utan i
  // årsredovisningen. Samhällsnämndens ändring saknar beslut.
  const rev = page.getByTestId('revideringstabell')
  const socRev = rev.locator('tr[data-organ="Socialnämnden"]')
  await expect(socRev).toContainText('+12,1 mnkr')
  await expect(rev.locator('[data-beslut="KF 2026-06-15 108"]').first()).toContainText('§ 108')
  await expect(rev.locator('[data-beslut="KF 2026-06-15 108"]').first()).toContainText('Protokollet finns inte i Kommunkollen')
  await expect(rev.locator('tr[data-organ="Skolnämnden"]')).toContainText('+5,6 mnkr')
  const ksRev = rev.locator('tr[data-organ="Kommunstyrelsen"]')
  await expect(ksRev).toContainText('Protokollet finns inte i Kommunkollen')
  await expect(ksRev.getByTestId('belopp-ur-dokument').getByRole('link')).toHaveAttribute('href', /arsredovisning-2027\.pdf#page=82$/)
  const rest = rev.locator('tr[data-rest="ja"]')
  await expect(rest).toHaveCount(1)
  await expect(rest).toContainText('Ej kopplat till beslut')
  await expect(rest).toContainText('Samhällsnämnden')
  await expect(rest).toContainText('+1,6 mnkr')

  // Orsakerna till avvikelserna som citat vid nämnden, med sidan i dokumentet.
  const socOrsak = page.getByTestId('namndtabell').locator('tr[data-orsak="Socialnämnden"]')
  await expect(socOrsak.locator('blockquote')).toHaveText([
    'Socialnämndens underskott beror främst på högre kostnader för placeringar än budgeterat.',
    'Socialnämnden prognostiserar ett underskott inom äldreomsorgen.',
  ])
  await expect(socOrsak.getByRole('link', { name: 'Årsredovisning 2027, s. 81' })).toHaveAttribute('href', /arsredovisning-2027\.pdf#page=81$/)
  await expect(socOrsak.getByRole('link', { name: 'Delårsrapport augusti 2027, s. 25' })).toBeVisible()
  await expect(page.getByTestId('namndtabell').locator('tr[data-orsak="Kommunstyrelsen"]')).toHaveCount(0)
  await expect(page.getByTestId('allmanna-orsaker')).toContainText('återfinns i respektive nämndsrapport')
})
