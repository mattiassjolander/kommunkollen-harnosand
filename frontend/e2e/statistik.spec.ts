import { expect, test } from '@playwright/test'
import { API_PORT } from '../playwright.config'

test.beforeAll(async ({ request }) => {
  test.setTimeout(180_000)
  const api = `http://127.0.0.1:${API_PORT}`
  expect((await request.post(`${api}/api/auth/test/redaktor`)).ok()).toBeTruthy()
  expect((await request.post(`${api}/api/insamlingar`)).ok()).toBeTruthy()
})

test('statistik över behandlingar per år, organ och typ, med filter i URL:en', async ({ page }) => {
  await page.request.post('/api/auth/logga-ut')
  await page.goto('/politik')
  await page.getByRole('navigation', { name: 'Huvudvyer' }).getByRole('link', { name: 'Statistik' }).click()
  await expect(page).toHaveURL(/\/politik\/statistik$/)
  await expect(page.getByTestId('automatiskt-tolkad')).toBeVisible()
  await expect(page.getByTestId('nyckeltal')).toContainText('Motion')
  await expect(page.getByTestId('teckenforklaring')).toContainText('Informationsärende')
  await expect(page.getByTestId('segment').first()).toBeVisible()
  await expect(page.getByTestId('statistikrad').first()).toBeVisible()
  await expect(page.getByTestId('csv')).toHaveAttribute('download', /\.csv$/)

  // Organ och årsintervall speglas i URL:en, och vyn går att öppna direkt från länken.
  const ar = await page.getByTestId('filter-fran').locator('option').allTextContents()
  const sista = ar[ar.length - 1]
  await page.getByTestId('filter-organ').selectOption('KF')
  await page.getByTestId('filter-fran').selectOption(sista)
  await page.getByTestId('filter-till').selectOption(sista)
  await expect(page).toHaveURL(new RegExp(`organ=KF.*fran=${sista}.*till=${sista}|fran=${sista}.*till=${sista}`))
  await page.reload()
  const rader = page.getByTestId('statistikrad')
  await expect(rader.first()).toHaveAttribute('data-organ', 'KF')
  for (const r of await rader.all()) {
    await expect(r).toHaveAttribute('data-ar', sista)
    await expect(r).toHaveAttribute('data-organ', 'KF')
  }

  // Ett omvänt intervall avvisas.
  if (ar.length > 1) {
    await page.getByTestId('filter-fran').selectOption(sista)
    await page.getByTestId('filter-till').selectOption(ar[0])
    await expect(page.getByTestId('omvant')).toBeVisible()
  }
})

test('behandlingens typ visas och kan rättas av en redaktör', async ({ page }) => {
  await page.request.post('/api/auth/test/redaktor')
  await page.goto('/politik?organ=KF')
  await page.locator('[data-testid="sammantrade"][data-datum="2026-03-23"]').getByRole('rowheader').getByRole('link').click()
  await page.getByTestId('behandling').first().getByRole('link').first().click()
  await expect(page.getByTestId('typ')).toContainText('Typ:')
  const nu = (await page.getByTestId('typ').textContent()) ?? ''
  const formular = page.getByTestId('rattelseformular')
  await formular.getByTestId('rattelse-uppgift').selectOption('typ')
  await formular.getByTestId('rattelse-varde').selectOption(nu.includes('Formalia') ? 'information' : 'formalia')
  await formular.getByTestId('rattelse-motivering').fill('Prov av typrättelse.')
  await formular.getByTestId('felet-i-inlasningen').check()
  await formular.getByTestId('spara-rattelse').click()
  await expect(formular.getByTestId('rattelse-sparad')).toBeVisible()
})

test('typerna i statistiken går att välja och visar behandlingarna', async ({ page }) => {
  await page.request.post('/api/auth/logga-ut')
  await page.goto('/politik/statistik')
  await page.getByTestId('nyckeltal').locator('[data-typ="motion"]').click()
  await expect(page).toHaveURL(/typ=motion/)
  const lista = page.getByTestId('typlista')
  await expect(lista).toContainText('Motion')
  await expect(page.getByTestId('typbehandling').first()).toContainText(/motion/i)
  await page.getByTestId('typbehandling').first().getByRole('link').first().click()
  await expect(page).toHaveURL(/\/politik\/sammantraden\/\d+\/paragraf\/\d+/)
})

test('motioner med väckt, motionär och länk till protokollet', async ({ page }) => {
  await page.request.post('/api/auth/logga-ut')
  await page.goto('/politik/statistik?organ=KF')
  const motioner = page.getByTestId('motioner')
  await expect(motioner.getByTestId('vackta')).not.toHaveText('0')
  const friskvard = page.getByTestId('motion').filter({ hasText: 'friskvårdsbidraget' })
  await expect(friskvard).toContainText('Olle Löfgren (L)')
  await expect(friskvard).toContainText('Obesvarad')
  await friskvard.getByRole('link', { name: /2026/ }).click()
  await expect(page).toHaveURL(/\/politik\/sammantraden\/\d+\/paragraf\/\d+/)
  await expect(page.locator('h1, h2').filter({ hasText: 'friskvårdsbidraget' }).first()).toBeVisible()
})

test('avvikelser i protokollen samlas på en sida', async ({ page }) => {
  await page.request.post('/api/auth/logga-ut')
  await page.goto('/politik')
  await page.getByRole('navigation', { name: 'Huvudvyer' }).getByRole('link', { name: 'Avvikelser' }).click()
  await expect(page).toHaveURL(/\/politik\/avvikelser$/)
  await expect(page.getByTestId('avvikelse-sammantrade').or(page.getByTestId('inga')).first()).toBeVisible()
  if (await page.getByTestId('avvikelse-sammantrade').count()) {
    const forsta = page.getByTestId('avvikelse-sammantrade').first()
    await expect(forsta.getByRole('link', { name: 'Originalprotokollet' })).toHaveAttribute('href', /^http/)
  }
  await page.getByTestId('filter-kategori').selectOption('motsagelse')
  await expect(page).toHaveURL(/kategori=motsagelse/)
  for (const s of await page.getByTestId('avvikelse-sammantrade').all()) {
    await expect(s.getByTestId('i-protokollet')).toBeVisible()
  }
  await expect(page.getByTestId('csv')).toHaveAttribute('download', /\.csv$/)
})

test('återkommande ärenden listas och går att öppna', async ({ page }) => {
  await page.request.post('/api/auth/logga-ut')
  await page.goto('/politik/statistik')
  const sektion = page.getByTestId('aterkommande')
  await expect(sektion).toBeVisible()
  const arenden = page.getByTestId('aterkommande-arende')
  if (await arenden.count()) {
    await arenden.first().getByRole('link').first().click()
    await expect(page).toHaveURL(/\/politik\/arenden\/\d+/)
  } else {
    await expect(sektion).toContainText('Inga återkommande ärenden')
  }
})

test('redaktören rättar en motion utan motionär, utgivaren publicerar och läsaren ser motionären (#78)', async ({ page }) => {
  // Redaktören hittar motionen i arbetslistan och väljer en person ur registret.
  await page.request.post('/api/auth/test/redaktor')
  await page.goto('/politik/statistik?organ=KF')
  await page.getByTestId('utan-motionar').check()
  const motion = page.getByTestId('motion').first()
  await expect(motion.getByTestId('motionarer')).toContainText('Uppgift saknas')
  const arende = await motion.getAttribute('data-arende')
  await motion.getByTestId('ratta-motionarer').click()

  const formular = page.getByTestId('motionarformular')
  await formular.getByTestId('motionar-sok').fill('Olle Löf')
  await formular.getByTestId('motionar-traff').filter({ hasText: 'Olle Löfgren' }).click()
  const rad = formular.getByTestId('motionarrad').first()
  await expect(rad).toContainText('Olle Löfgren')
  // Partiet förifylls, med källan, och går att ändra.
  await expect(rad.getByTestId('motionar-parti')).toHaveValue('L')
  await expect(rad.getByTestId('parti-kalla')).toBeVisible()
  await formular.getByTestId('motionar-motivering').fill('Motionen är undertecknad av Olle Löfgren (L).')
  await formular.getByTestId('felet-i-inlasningen').check()
  await formular.getByTestId('spara-motionarer').click()
  await expect(page.getByTestId('motionarer-sparade')).toBeVisible()

  // Utgivaren granskar och publicerar.
  await page.request.post('/api/auth/test/utgivare')
  await page.goto('/redaktion/rattelser')
  const utkast = page.getByTestId('rattelser-utkast').getByTestId('rattelse').filter({ hasText: 'Motionärer' })
  await expect(utkast.getByTestId('nytt')).toHaveText('Olle Löfgren (L)')
  await utkast.getByTestId('granska').click()
  await page.getByTestId('rattelser-granskad').getByTestId('rattelse').filter({ hasText: 'Motionärer' }).getByTestId('publicera').click()
  await expect(page.getByTestId('rattelser-publicerad').getByTestId('rattelse').filter({ hasText: 'Motionärer' })).toHaveCount(1)

  // Läsaren ser motionären med parti, länk till personsidan och rättelsemarkering.
  await page.request.post('/api/auth/logga-ut')
  await page.goto('/politik/statistik?organ=KF')
  const rattad = page.locator(`[data-testid="motion"][data-arende="${arende}"]`)
  const celler = rattad.getByTestId('motionarer')
  await expect(celler).toContainText('Olle Löfgren (L)')
  await expect(celler).not.toContainText('Uppgift saknas')
  const markering = celler.getByTestId('rattad')
  await markering.locator('summary').click()
  await expect(markering.getByTestId('ursprungligt')).toHaveText('inget')
  await celler.getByRole('link', { name: 'Olle Löfgren' }).click()
  await expect(page).toHaveURL(/\/politik\/ledamoter\/\d+$/)
})
