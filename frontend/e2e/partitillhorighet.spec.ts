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

// Söm 2 (#100, del 2): redaktören ändrar ett förslag och bekräftar det i en batch, en utgivare publicerar
// batchen, och läsaren ser partiet med markering och vad protokollet anger. Perioderna återkallas sist.
test('förslag bekräftas i en batch och publiceras tillsammans', async ({ page, request }) => {
  await request.post(`${api}/api/auth/test/redaktor`)
  const forslag = await (await request.get(`${api}/api/partitillhorighet/forslag`)).json()
  const person = forslag.find(
    (f: { perioder: { parti: string; krockar: unknown[] }[] }) =>
      f.perioder.length === 1 && f.perioder[0].parti !== '-' && !f.perioder[0].krockar.length,
  )
  expect(person).toBeTruthy()

  await page.request.post('/api/auth/test/redaktor')
  await page.goto('/politik/partitillhorighet')
  const sektion = page.getByTestId('periodforslag')
  await sektion.getByTestId('forslag-sok').fill(person.ledamot.namn)
  const rad = sektion.locator(`[data-testid="forslag"][data-ledamot="${person.ledamot.id}"]`)
  await expect(rad.getByTestId('forslag-parti')).toHaveValue(person.perioder[0].parti)
  await expect(rad.getByTestId('belagg')).toContainText(String(person.perioder[0].antal_per_parti[person.perioder[0].parti]))
  await rad.getByTestId('forslag-parti').fill('-')
  await rad.getByTestId('forslag-motivering').fill('Partilös enligt prov.')
  await rad.getByTestId('valj').check()
  await sektion.getByTestId('bekrafta-forslag').click()
  await expect(page.getByTestId('batch-sparad')).toContainText('1 period är sparad som utkast')
  await expect(sektion.locator(`[data-testid="forslag"][data-ledamot="${person.ledamot.id}"]`)).toHaveCount(0)

  await page.request.post('/api/auth/test/utgivare')
  await page.goto('/politik/partitillhorighet')
  await page.getByTestId('perioder-utkast').locator('..').getByTestId('granska-batch').first().click()
  await page.getByTestId('publicera-batch').first().click()
  await expect(page.getByTestId('perioder-publicerad').getByTestId('period')).toHaveCount(1)

  // Läsaren ser partiet med markering och vad protokollet anger.
  await page.request.post('/api/auth/logga-ut')
  const sida = await (await request.get(`${api}/api/ledamoter/${person.ledamot.id}`)).json()
  const s = sida.sammantraden.find((x: { partitillhorighet: unknown }) => x.partitillhorighet)
  await page.goto(`/politik/sammantraden/${s.sammantrade.id}`)
  const markering = page.getByTestId('person').filter({ hasText: s.namn }).first().getByTestId('partitillhorighet')
  await expect(markering).toContainText('Fastställt av redaktionen')
  await markering.locator('summary').click()
  await expect(markering).toHaveAttribute('data-protokollet', person.perioder[0].parti)
  await expect(markering).toContainText('Partilös enligt prov.')

  // Återkalla, så att protokollens uppgifter gäller igen för följande tester.
  await request.post(`${api}/api/auth/test/utgivare`)
  for (const t of await (await request.get(`${api}/api/partitillhorighet?status=publicerad`)).json()) {
    expect((await request.post(`${api}/api/partitillhorighet/${t.id}/aterkallelse`, { data: { motivering: 'Test.' } })).ok()).toBeTruthy()
  }
})

// Söm 2 (#100, del 3): en krock syns i fliken, redaktören bekräftar den som fel i protokollet, och när rättelsen är
// publicerad är protokollet märkt med felaktigheter. Rättelsen och perioden återkallas sist.
test('en krock bekräftas som fel i protokollet', async ({ page, request }) => {
  const sammantrade = (await (await request.get(`${api}/api/sammantraden?organ=KF`)).json()).find(
    (s: { datum: string }) => s.datum === '2026-03-23',
  )
  const narvaro = (await (await request.get(`${api}/api/sammantraden/${sammantrade.id}`)).json()).narvaro
  const person = narvaro.find(
    (p: { parti: string | null; ledamot_id: number | null; kategori: string; parti_harlett?: unknown }) =>
      p.parti && p.parti !== '-' && p.ledamot_id && p.kategori === 'beslutande' && !p.parti_harlett,
  )
  await request.post(`${api}/api/auth/test/redaktor`)
  const period = await (await request.post(`${api}/api/partitillhorighet`, {
    data: { ledamot_id: person.ledamot_id, parti: '-', fran: '2026-03-23', till: '2026-03-23', motivering: 'Prov.' },
  })).json()
  await request.post(`${api}/api/auth/test/utgivare`)
  await request.post(`${api}/api/partitillhorighet/${period.id}/granskning`)
  await request.post(`${api}/api/partitillhorighet/${period.id}/publicering`)

  await page.request.post('/api/auth/test/redaktor')
  await page.goto('/politik/partitillhorighet')
  await page.getByTestId('filter-krockar').click()
  await expect(page.locator(`[data-testid="periodperson"][data-ledamot="${person.ledamot_id}"] [data-testid="antal-krockar"]`)).toHaveText('1')
  const krock = page.locator(`[data-testid="krockperson"][data-ledamot="${person.ledamot_id}"] [data-testid="krock"]`)
  await expect(krock).toHaveCount(1)
  await expect(krock).toContainText('protokollet anger')
  await krock.getByTestId('valj-krock').check()
  const formular = page.getByTestId('bekrafta-krockar-formular')
  await formular.getByTestId('felet-i-protokollet').check()
  await formular.getByTestId('krock-motivering').fill('Partilös enligt beslut i fullmäktige.')
  await formular.getByTestId('bekrafta-krockar').click()
  await expect(page.getByTestId('krockar-bekraftade')).toContainText('1 krock är bekräftad')
  await expect(krock).toHaveCount(0)

  // Utgivaren publicerar rättelsen, och protokollet är märkt med felaktigheter.
  await request.post(`${api}/api/auth/test/utgivare`)
  const rattelse = (await (await request.get(`${api}/api/rattelser?status=utkast`)).json()).find(
    (r: { namn: string; sammantrade: { id: number } }) => r.namn === person.namn && r.sammantrade.id === sammantrade.id,
  )
  await request.post(`${api}/api/rattelser/${rattelse.id}/granskning`)
  await request.post(`${api}/api/rattelser/${rattelse.id}/publicering`)
  await page.request.post('/api/auth/logga-ut')
  await page.goto(`/politik/sammantraden/${sammantrade.id}`)
  await expect(page.getByTestId('felaktigheter')).toContainText('Innehåller felaktigheter')

  for (const [url, motivering] of [
    [`${api}/api/rattelser/${rattelse.id}/aterkallelse`, 'Test.'],
    [`${api}/api/partitillhorighet/${period.id}/aterkallelse`, 'Test.'],
  ]) {
    expect((await request.post(url, { data: { motivering } })).ok()).toBeTruthy()
  }
})
