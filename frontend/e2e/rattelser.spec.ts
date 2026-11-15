import { expect, test } from '@playwright/test'
import { API_PORT } from '../playwright.config'

const api = `http://127.0.0.1:${API_PORT}`

test.beforeAll(async ({ request }) => {
  test.setTimeout(180_000)
  expect((await request.post(`${api}/api/auth/test/redaktor`)).ok()).toBeTruthy()
  expect((await request.post(`${api}/api/insamlingar?kalla=harnosand-protokoll-kf`)).ok()).toBeTruthy()
})

test('en rättelse från utkast till publicerad, sedd som läsare', async ({ page }) => {
  // Redaktören rättar beslutet i den första behandlingen vid KF 2026-03-23.
  await page.request.post('/api/auth/test/redaktor')
  await page.goto('/politik?organ=KF')
  await page.locator('[data-testid="sammantrade"][data-datum="2026-03-23"]').getByRole('link').click()
  await page.getByTestId('behandling').first().getByRole('link').click()
  await expect(page).toHaveURL(/\/paragraf\/\d+$/)
  const tolkat = (await page.getByTestId('beslut').textContent())?.trim()
  const adress = page.url()

  const formular = page.getByTestId('rattelseformular')
  await formular.getByTestId('rattelse-uppgift').selectOption('beslut')
  await formular.getByTestId('rattelse-varde').fill('Kommunfullmäktige godkänner dagordningen med ändringar.')
  await formular.getByTestId('rattelse-motivering').fill('Beslutet på sidan 3.')
  await formular.getByTestId('spara-rattelse').click()
  await expect(formular.getByTestId('rattelse-sparad')).toBeVisible()

  // Utkastet syns inte för läsaren.
  await page.request.post('/api/auth/logga-ut')
  await page.goto(adress)
  await expect(page.getByTestId('beslut')).toHaveText(tolkat ?? '')
  await expect(page.getByTestId('ratta')).toHaveCount(0)

  // Utgivaren granskar och publicerar.
  await page.request.post('/api/auth/test/utgivare')
  await page.goto('/politik')
  await page.getByRole('navigation', { name: 'Politik och beslut' }).getByRole('link', { name: 'Rättelser' }).click()
  const utkast = page.getByTestId('rattelser-utkast').getByTestId('rattelse').first()
  await expect(utkast.getByTestId('nytt')).toHaveText('Kommunfullmäktige godkänner dagordningen med ändringar.')
  await utkast.getByTestId('granska').click()
  const granskad = page.getByTestId('rattelser-granskad').getByTestId('rattelse').first()
  await granskad.getByTestId('publicera').click()
  await expect(page.getByTestId('rattelser-publicerad').getByTestId('rattelse')).toHaveCount(1)

  // Läsaren ser den rättade uppgiften med markering och vad tolkningen sa.
  await page.request.post('/api/auth/logga-ut')
  await page.goto(adress)
  await expect(page.getByTestId('beslut')).toHaveText('Kommunfullmäktige godkänner dagordningen med ändringar.')
  const markering = page.locator('[data-testid="rattad"][data-falt="beslut"]')
  await expect(markering).toContainText('Rättad av redaktionen')
  await markering.locator('summary').click()
  await expect(markering.getByTestId('ursprungligt')).toHaveText(tolkat ?? '')
  await expect(markering).toContainText('Beslutet på sidan 3.')
})

test('en redaktör som också är utgivare kan inte godkänna sin egen rättelse', async ({ page }) => {
  await page.request.post('/api/auth/test/redaktor+utgivare')
  await page.goto('/politik?organ=KF')
  await page.locator('[data-testid="sammantrade"][data-datum="2026-03-23"]').getByRole('link').click()
  await page.getByTestId('behandling').nth(1).getByRole('link').click()
  const formular = page.getByTestId('rattelseformular')
  await formular.getByTestId('rattelse-uppgift').selectOption('rubrik')
  await formular.getByTestId('rattelse-varde').fill('Rättad rubrik')
  await formular.getByTestId('rattelse-motivering').fill('Rubriken i protokollet.')
  await formular.getByTestId('spara-rattelse').click()
  await formular.getByRole('link', { name: 'Till rättelserna' }).click()

  const egen = page.getByTestId('rattelser-utkast').getByTestId('rattelse').filter({ hasText: 'Rättad rubrik' })
  await expect(egen.getByTestId('egen')).toBeVisible()
  await expect(egen.getByTestId('granska')).toHaveCount(0)
  await egen.getByTestId('ta-bort').click()
  await expect(egen).toHaveCount(0)
  await page.request.post('/api/auth/logga-ut')
})

test('en redaktör rättar partiet i närvarolistan från sammanträdet', async ({ page }) => {
  await page.request.post('/api/auth/logga-ut')
  await page.goto('/politik?organ=KF')
  await page.locator('[data-testid="sammantrade"][data-datum="2026-02-23"]').getByRole('link').click()
  await expect(page.getByTestId('narvaro')).toBeVisible()
  await expect(page.getByTestId('rattelseformular')).toHaveCount(0)

  await page.request.post('/api/auth/test/redaktor')
  await page.reload()
  const formular = page.getByTestId('rattelseformular')
  const forsta = await formular.getByTestId('rattelse-uppgift').locator('option').first().getAttribute('value')
  expect(forsta).toMatch(/^parti:/)
  await formular.getByTestId('rattelse-varde').fill('-')
  await formular.getByTestId('rattelse-motivering').fill('Närvarolistan på sidan 2.')
  await formular.getByTestId('spara-rattelse').click()
  await expect(formular.getByTestId('rattelse-sparad')).toBeVisible()
})
