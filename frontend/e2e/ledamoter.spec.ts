import { expect, test } from '@playwright/test'
import { API_PORT } from '../playwright.config'

const api = `http://127.0.0.1:${API_PORT}`

test.beforeAll(async ({ request }) => {
  test.setTimeout(180_000) // insamlingen tolkar ett femtiotal protokoll
  expect((await request.post(`${api}/api/auth/test/redaktor`)).ok()).toBeTruthy()
  expect((await request.post(`${api}/api/insamlingar?kalla=harnosand-protokoll-kf`)).ok()).toBeTruthy()
})

test('från behandling till ledamot till ledamotens sammanträden', async ({ page }) => {
  await page.goto('/politik?organ=KF')
  await page.locator('[data-testid="sammantrade"][data-datum="2026-02-23"]').getByRole('rowheader').getByRole('link').click()
  await page.locator('[data-testid="behandling"][data-paragraf="3"]').getByRole('link').click()
  await expect(page).toHaveURL(/\/paragraf\/3$/)

  const person = page.getByTestId('beslutande').getByTestId('person').filter({ hasText: 'Lennart Molin' })
  await expect(person.getByTestId('parti')).toHaveText('S')
  await person.getByRole('link', { name: 'Lennart Molin' }).click()

  await expect(page).toHaveURL(/\/politik\/ledamoter\/\d+$/)
  await expect(page.getByRole('heading', { name: 'Lennart Molin', level: 1 })).toBeVisible()
  await expect(page.getByTestId('automatiskt-tolkad')).toBeVisible()
  await expect(page.getByTestId('partiperiod').first().getByTestId('parti')).toHaveAttribute('data-parti', 'S')
  await expect(page.locator('[data-testid="organrad"][data-organ="KF"]')).toContainText('Kommunfullmäktige')

  const rad = page.locator('[data-testid="ledamotens-sammantrade"][data-datum="2026-02-23"]')
  await expect(rad).toContainText('tjänstgör för Nina Skyttberg')
  await rad.getByRole('link').click()
  await expect(page).toHaveURL(/\/politik\/sammantraden\/\d+$/)
  await expect(page.getByTestId('sammantradesinfo')).toContainText('23 februari 2026')
})

test('registret visar parti enligt protokollen och ett partibyte', async ({ page }) => {
  await page.goto('/politik')
  await page.getByRole('navigation', { name: 'Politik och beslut' }).getByRole('link', { name: 'Ledamöter' }).click()
  await expect(page).toHaveURL(/\/politik\/ledamoter$/)

  await page.getByTestId('sok-ledamot').fill('Carl-Fredrik')
  await expect(page).toHaveURL(/q=Carl-Fredrik/)
  const edgren = page.getByTestId('ledamot')
  await expect(edgren).toHaveCount(1)
  await expect(edgren.getByTestId('parti').first()).toHaveText('partilös')
  await expect(edgren.getByTestId('flera-partier')).toContainText('tidigare även V')

  await edgren.getByRole('link').click()
  const perioder = page.getByTestId('partiperiod')
  await expect(perioder.first()).toContainText('partilös')
  await expect(perioder.last()).toContainText('V')

  // Partiet visas alltid med förkortning. Färgen är bara en prick bredvid.
  await page.goto('/politik/ledamoter?parti=MP')
  for (const p of await page.getByTestId('ledamot').getByTestId('parti').all()) {
    await expect(p).toHaveText(/^(MP|S|V|M|C|L|KD|SD|partilös|parti anges inte i protokollet)$/)
  }
})

test('en redaktör slår ihop två namn för samma person och delar upp dem igen', async ({ page }) => {
  // Läsare ser inga redaktörsverktyg.
  await page.goto('/politik/ledamoter?q=Mohamed')
  const rader = page.getByTestId('ledamot')
  await expect(rader).toHaveCount(2)
  await page.getByRole('link', { name: 'Mohamed Abdulwahab', exact: true }).click()
  await expect(page.getByRole('heading', { name: 'Mohamed Abdulwahab', level: 1 })).toBeVisible()
  await expect(page.getByTestId('redaktor')).toHaveCount(0)

  expect((await page.request.post('/api/auth/test/redaktor')).ok()).toBeTruthy()
  await page.reload()
  const red = page.getByTestId('redaktor')
  await red.getByTestId('sok-annan').fill('Mohamed Mohamed')
  await red.getByTestId('forslag').filter({ hasText: 'Mohamed Mohamed Abdulwahab' }).getByTestId('sla-ihop').click()
  await expect(red.getByTestId('meddelande')).toContainText('Mohamed Mohamed Abdulwahab är nu sammanslagen med Mohamed Abdulwahab')
  await expect(page.getByTestId('andra-namn')).toContainText('Mohamed Mohamed Abdulwahab')

  await page.goto('/politik/ledamoter?q=Mohamed')
  await expect(page.getByTestId('ledamot')).toHaveCount(1)
  await page.getByTestId('ledamot').getByRole('link').click()

  await page.getByTestId('redaktor').getByTestId('namnvariant').filter({ hasText: 'Mohamed Mohamed' }).getByTestId('dela-upp').click()
  await expect(page.getByTestId('meddelande')).toContainText('är nu en egen person igen')
  await page.goto('/politik/ledamoter?q=Mohamed')
  await expect(page.getByTestId('ledamot')).toHaveCount(2)
})
