import { expect, test } from '@playwright/test'

// Söm 2 (#48, #58): planförutsättningarna och budgetförslagen för 2027 är inlästa som utkast när
// servern startar (`--budgetforslag tests/fixtures/budgetforslag`). Utgivaren granskar och publicerar
// dem, och läsaren jämför förslagen mot planförutsättningarna och den antagna budgeten.

test('läsaren jämför budgetförslagen mot planförutsättningarna', async ({ page }) => {
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

  // Resultat-, investerings-, balans- och kassaflödesbudget visas en gång för budgetåret.
  const pf = page.getByTestId('planforutsattningar')
  await expect(pf.locator('table')).toHaveCount(4)
  await expect(pf.locator('[data-tabell="investeringar"] tr', { hasText: 'Totalt' })).toContainText('147,0 mnkr')
  await expect(pf.locator('[data-tabell="kassaflode"] tr', { hasText: 'Totalt kassaflöde' })).toContainText('47,0 mnkr')
})
