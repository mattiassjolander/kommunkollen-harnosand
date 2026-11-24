import { expect, test } from '@playwright/test'

// Navigeringen (#146): undervyer i vänsternavigeringen, Redaktion som egen huvudvy,
// fast sidospalt och meny på smal skärm.

test('läsaren byter undervy i Politik och beslut och ser vyns namn som rubrik', async ({ page }) => {
  await page.goto('/')
  const nav = page.getByRole('navigation', { name: 'Huvudvyer' })
  // Undervyerna syns först när man är i huvudvyn, och Redaktion syns inte för läsaren.
  await expect(nav.getByRole('link', { name: 'Statistik' })).toHaveCount(0)
  await expect(nav.getByRole('link', { name: 'Redaktion' })).toHaveCount(0)

  await nav.getByRole('link', { name: 'Politik och beslut' }).click()
  await expect(page).toHaveURL(/\/politik$/)
  await expect(nav.getByRole('link', { name: 'Politik och beslut' })).toHaveAttribute('aria-expanded', 'true')
  await expect(nav.getByRole('link', { name: 'Sammanträden' })).toHaveAttribute('aria-current', 'page')

  await nav.getByRole('link', { name: 'Statistik' }).click()
  await expect(page).toHaveURL(/\/politik\/statistik$/)
  await expect(page.getByRole('heading', { name: 'Statistik', level: 1 })).toBeVisible()
  await expect(page.getByTestId('brodsmula')).toHaveText('Politik och beslut ›')
  await expect(nav.getByRole('link', { name: 'Statistik' })).toHaveAttribute('aria-current', 'page')
  await expect(page).toHaveTitle('Statistik · Politik och beslut · Kommunkollen Härnösand')

  // Brödsmulan leder tillbaka till huvudvyns första undervy.
  await page.getByTestId('brodsmula').getByRole('link', { name: 'Politik och beslut' }).click()
  await expect(page.getByRole('heading', { name: 'Sammanträden', level: 1 })).toBeVisible()

  // Ekonomi fungerar likadant.
  await nav.getByRole('link', { name: 'Ekonomi', exact: true }).click()
  await expect(page.getByRole('heading', { name: 'Nyckeltal', level: 1 })).toBeVisible()
  await nav.getByRole('link', { name: 'Budget och utfall' }).click()
  await expect(page.getByRole('heading', { name: 'Budget och utfall', level: 1 })).toBeVisible()
  await expect(page.getByTestId('brodsmula')).toHaveText('Ekonomi ›')
})

test('logotypen och användarrutan syns längst ner även efter skrollning', async ({ page }) => {
  await page.setViewportSize({ width: 1280, height: 700 })
  await page.goto('/politik/statistik')
  await expect(page.getByRole('heading', { name: 'Statistik', level: 1 })).toBeVisible()
  await page.mouse.wheel(0, 5000)
  await page.evaluate(() => window.scrollTo(0, document.body.scrollHeight))
  const ruta = page.getByTestId('anvandare')
  await expect(ruta).toBeInViewport()
  const box = await ruta.boundingBox()
  expect(box!.y + box!.height).toBeLessThanOrEqual(700)
  expect(box!.y + box!.height).toBeGreaterThan(600)
})

test('utgivaren öppnar Redaktion › Rättelser, och gamla adresser styrs om', async ({ page }) => {
  await page.request.post('/api/auth/test/utgivare')
  await page.goto('/')
  const nav = page.getByRole('navigation', { name: 'Huvudvyer' })
  await nav.getByRole('link', { name: 'Redaktion' }).click()
  await expect(page).toHaveURL(/\/redaktion\/rattelser$/)
  await expect(page.getByRole('heading', { name: 'Rättelser', level: 1 })).toBeVisible()
  await expect(page.getByTestId('brodsmula')).toHaveText('Redaktion ›')
  // Utgivaren ser inte redaktörens verktyg för kopplingar och sammanträdesplaner.
  await expect(nav.getByRole('link', { name: /^Kopplingar/ })).toHaveCount(0)
  await expect(nav.getByRole('link', { name: 'Budgetutkast' })).toBeVisible()
  await expect(nav.getByText('Granska')).toBeVisible()
  await expect(nav.getByText('Registrera')).toBeVisible()

  await page.goto('/politik/partitillhorighet')
  await expect(page).toHaveURL(/\/redaktion\/partitillhorighet$/)
  await expect(page.getByRole('heading', { name: 'Partitillhörighet', level: 1 })).toBeVisible()
})

test('på smal skärm öppnas navigeringen med en menyknapp', async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 800 })
  await page.goto('/politik')
  const knapp = page.getByTestId('menyknapp')
  const nav = page.getByRole('navigation', { name: 'Huvudvyer' })
  await expect(knapp).toHaveAttribute('aria-expanded', 'false')
  await expect(nav).toBeHidden()

  await knapp.click()
  await expect(knapp).toHaveAttribute('aria-expanded', 'true')
  await expect(nav).toBeVisible()
  await expect(page.getByTestId('anvandare')).toBeInViewport()

  // Esc stänger menyn och lämnar fokus på knappen.
  await page.keyboard.press('Escape')
  await expect(nav).toBeHidden()
  await expect(knapp).toBeFocused()

  // Ett val stänger menyn.
  await knapp.click()
  await nav.getByRole('link', { name: 'Ledamöter' }).click()
  await expect(page).toHaveURL(/\/politik\/ledamoter$/)
  await expect(nav).toBeHidden()
  await expect(page.getByRole('heading', { name: 'Ledamöter', level: 1 })).toBeVisible()
})
