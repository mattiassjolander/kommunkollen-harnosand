import { expect, test } from '@playwright/test'

// Söm 2 (#48): budgetförslagen för 2027 är inlästa som utkast när servern startar
// (`--budgetforslag tests/fixtures/budgetforslag`). Utgivaren publicerar dem, och läsaren jämför
// förslagen med varandra och med den antagna budgeten.

test('läsaren jämför budgetförslagen för ett budgetår', async ({ page }) => {
  // Utgivaren granskar och publicerar utkasten (de som inte redan publicerats i en tidigare körning).
  await page.request.post('/api/auth/test/utgivare')
  await page.goto('/politik')
  await page.getByRole('navigation', { name: 'Politik och beslut' }).getByRole('link', { name: 'Budgetutkast' }).click()
  await expect(page.getByTestId('budgetutkast').or(page.getByTestId('inga-utkast')).first()).toBeVisible()
  // Utgivaren ser siffrorna med sidan i originalet innan hen granskar.
  const l = page.locator('[data-testid="budgetutkast"][data-nyckel="L"]')
  if ((await l.count()) > 0) {
    const ks = l.getByTestId('uppgifter').locator('tr', { hasText: 'Kommunstyrelsen' })
    await expect(ks).toContainText('150 (−37)')
    await expect(ks.getByRole('link', { name: 's. 1' })).toHaveAttribute('href', /\/original#page=1$/)
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
  // Den antagna budgeten först, sedan förslagen i alfabetisk ordning.
  await expect(kolumner).toHaveCount(3)
  await expect(kolumner.nth(0)).toHaveAttribute('data-nyckel', 'majoritet')
  await expect(kolumner.nth(0).getByTestId('antagen')).toHaveText('Antagen budget')
  await expect(kolumner.nth(1)).toHaveAttribute('data-nyckel', 'L')

  // Liberalernas ram för kommunstyrelsen och skillnaden mot den antagna budgeten.
  const ks = tabell.locator('tr[data-organ="Kommunstyrelsen"] td')
  await expect(ks.nth(0)).toContainText('191,3 mnkr')
  await expect(ks.nth(1)).toContainText('150,0 mnkr')
  await expect(ks.nth(1).getByTestId('differens')).toHaveText('−41,3 mnkr (−21,6 %)')
  // Moderaterna anger bara förändringen.
  await expect(ks.nth(2)).toContainText('−37,0 mnkr')
  await expect(ks.nth(2)).toContainText('mot Planförutsättningar 2027')

  // Siffran länkar till sidan i originalet.
  await expect(ks.nth(0).getByRole('link')).toHaveAttribute('href', /\/api\/budgetforslag\/\d+\/original#page=4$/)

  // Planåren visas för sig, och valet speglas i adressen.
  await page.getByTestId('filter-visa').selectOption('2028')
  await expect(page).toHaveURL(/visa=2028/)
  await expect(tabell.locator('tr[data-organ="Socialnämnden"] td').nth(0)).toContainText('921,7 mnkr')
  await expect(tabell.locator('tr[data-organ="Socialnämnden"] td').nth(1)).toContainText('Anges inte')
})
