import { expect, test } from '@playwright/test'
import { API_PORT } from '../playwright.config'

const api = `http://127.0.0.1:${API_PORT}`

test.beforeAll(async ({ request }) => {
  test.setTimeout(180_000)
  expect((await request.post(`${api}/api/auth/test/redaktor`)).ok()).toBeTruthy()
  expect((await request.post(`${api}/api/insamlingar?kalla=harnosand-protokoll-kf`)).ok()).toBeTruthy()
})

// Söm 2 (#100): redaktören fastställer partiet för en period, utgivaren publicerar, och läsaren ser partiet med
// markering och vad protokollet anger. Perioden återkallas sist, så att protokollens uppgifter gäller igen.
test('en fastställd partitillhörighet från personsidan till sammanträdet', async ({ page, request }) => {
  const sammantrade = (await (await request.get(`${api}/api/sammantraden?organ=KF`)).json()).find(
    (s: { datum: string }) => s.datum === '2026-03-23',
  )
  const narvaro = (await (await request.get(`${api}/api/sammantraden/${sammantrade.id}`)).json()).narvaro
  const person = narvaro.find(
    (p: { parti: string | null; ledamot_id: number | null; kategori: string; parti_harlett?: unknown }) =>
      p.parti && p.parti !== '-' && p.ledamot_id && p.kategori === 'beslutande' && !p.parti_harlett,
  )

  // Redaktören registrerar en period som partilös på personens sida.
  await page.request.post('/api/auth/test/redaktor')
  await page.goto(`/politik/ledamoter/${person.ledamot_id}`)
  const sektion = page.getByTestId('faststalld-partitillhorighet')
  await expect(sektion).toContainText('Ingen period är fastställd.')
  await sektion.getByTestId('period-parti').fill('-')
  await sektion.getByTestId('period-fran').fill('2026-01-01')
  await sektion.getByTestId('period-motivering').fill('Lämnade partiet enligt protokollet från december.')
  await sektion.getByTestId('spara-period').click()
  await expect(sektion.getByTestId('period-sparad')).toContainText('sparad som utkast')

  // Utkastet gäller inte.
  await page.request.post('/api/auth/logga-ut')
  await page.goto(`/politik/sammantraden/${sammantrade.id}`)
  const rad = page.getByTestId('person').filter({ hasText: person.namn }).first()
  await expect(rad.getByTestId('parti')).toHaveAttribute('data-parti', person.parti)
  await expect(rad.getByTestId('partitillhorighet')).toHaveCount(0)

  // Utgivaren granskar och publicerar under fliken Partitillhörighet.
  await page.request.post('/api/auth/test/utgivare')
  await page.goto('/politik')
  await page.getByRole('navigation', { name: 'Politik och beslut' }).getByRole('link', { name: 'Partitillhörighet' }).click()
  const utkast = page.getByTestId('perioder-utkast').getByTestId('period').first()
  await expect(utkast).toContainText(person.namn)
  await utkast.getByTestId('granska').click()
  await page.getByTestId('perioder-granskad').getByTestId('period').first().getByTestId('publicera').click()
  await expect(page.getByTestId('perioder-publicerad').getByTestId('period')).toHaveCount(1)

  // Läsaren ser partiet med markering och vad protokollet anger.
  await page.request.post('/api/auth/logga-ut')
  await page.goto(`/politik/sammantraden/${sammantrade.id}`)
  await expect(rad.getByTestId('parti')).toHaveAttribute('data-parti', '-')
  const markering = rad.getByTestId('partitillhorighet')
  await expect(markering).toContainText('Fastställt av redaktionen')
  await expect(markering).toHaveAttribute('data-protokollet', person.parti)
  await markering.locator('summary').click()
  await expect(markering).toContainText('2026-01-01 – tills vidare')
  await expect(markering).toContainText('Lämnade partiet enligt protokollet från december.')
  await page.goto(`/politik/ledamoter/${person.ledamot_id}`)
  await expect(page.getByTestId('faststalld-period')).toHaveCount(1)
  await expect(page.getByTestId('periodformular')).toHaveCount(0)

  // Utgivaren återkallar perioden, och protokollets uppgift gäller igen.
  await page.request.post('/api/auth/test/utgivare')
  await page.goto('/politik/partitillhorighet')
  const publicerad = page.getByTestId('perioder-publicerad').getByTestId('period').first()
  await publicerad.getByTestId('aterkalla').click()
  await publicerad.getByTestId('aterkalla-motivering').fill('Perioden var fel.')
  await publicerad.getByTestId('spara-aterkallelse').click()
  await expect(page.getByTestId('perioder-aterkallad').getByTestId('period')).toHaveCount(1)
  await page.request.post('/api/auth/logga-ut')
  await page.goto(`/politik/sammantraden/${sammantrade.id}`)
  await expect(rad.getByTestId('parti')).toHaveAttribute('data-parti', person.parti)
  await expect(rad.getByTestId('partitillhorighet')).toHaveCount(0)
})
