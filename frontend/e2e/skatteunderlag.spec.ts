import { expect, test } from '@playwright/test'
import { API_PORT } from '../playwright.config'

test.beforeAll(async ({ request }) => {
  test.setTimeout(300_000) // LibreOffice räknar om fem prognosfiler
  // Förbered data: samla in SKR:s skatteunderlagsprognoser från inspelningen (#61).
  const api = `http://127.0.0.1:${API_PORT}`
  expect((await request.post(`${api}/api/auth/test/redaktor`)).ok()).toBeTruthy()
  const svar = await request.post(`${api}/api/insamlingar?kalla=skr-skatteunderlagsprognos`, { timeout: 300_000 })
  expect(svar.ok()).toBeTruthy()
})

test('skatteunderlagsprognosen är öppen och visar senaste cirkuläret i mnkr med källa', async ({ page }) => {
  await page.goto('/ekonomi')
  await page.getByRole('navigation', { name: 'Huvudvyer' }).getByRole('link', { name: 'Skatteunderlagsprognos' }).click()
  await expect(page).toHaveURL(/\/ekonomi\/skatteunderlag$/)

  // Ingen inloggning krävs för att läsa.
  await expect(page.getByTestId('anvandare').getByRole('button', { name: 'Logga in' })).toBeVisible()

  const senaste = page.getByTestId('senaste-prognos')
  await expect(senaste.getByRole('heading', { name: 'Senaste prognosen, cirkulär 26:28' })).toBeVisible()
  await expect(senaste).toContainText('Publicerad 6 okt 2026')
  await expect(senaste).toContainText('23,34 %')

  const tabell = senaste.getByTestId('prognostabell')
  await expect(tabell.getByRole('columnheader', { name: '2033' })).toBeVisible()
  // Summa intäkter inklusive avräkning och fastighetsavgift 2027: 2 222 069 tkr.
  await expect(tabell.locator('[data-rad="summa_inkl"]')).toContainText(/2\s222,1 mnkr/)
  await expect(tabell.locator('[data-rad="invanare"]')).toContainText(/24\s360/)

  const kalla = senaste.getByRole('link', { name: 'Prognosunderlag-K-2026-2033-26028.xlsm' })
  await expect(kalla).toHaveAttribute('href', /skr\.se\/download\/.*26028\.xlsm$/)
})

test('diagrammet har en linje per cirkulär, tabellvy och CSV', async ({ page }) => {
  await page.goto('/ekonomi/skatteunderlag')
  const diagram = page.getByTestId('prognosdiagram')
  await expect(diagram.locator('path.linje')).toHaveCount(5)
  await expect(diagram.getByLabel('Teckenförklaring')).toContainText('Cirkulär 26:12')

  // Tooltip vid hover med år, värde, enhet och källa.
  await diagram.locator('svg').hover()
  const tips = diagram.getByRole('status')
  await expect(tips).toContainText('mnkr')
  await expect(tips).toContainText('SKR')

  await diagram.getByText('Visa som tabell').click()
  await expect(diagram.getByTestId('cirkulartabell').locator('tbody tr')).toHaveCount(5)
  // Inklusive avräkning: för 2026 syns den ändrade slutavräkningen, fast summa intäkter är densamma.
  const tabell = diagram.getByTestId('cirkulartabell')
  await expect(tabell.locator('tr[data-cirkular="26:12"] td').first()).toHaveText(/2\s136,5 mnkr/)
  await expect(tabell.locator('tr[data-cirkular="26:28"] td').first()).toHaveText(/2\s123,2 mnkr/)

  const nedladdning = page.waitForEvent('download')
  await diagram.getByTestId('exportera').click()
  expect((await nedladdning).suggestedFilename()).toBe('skatteunderlagsprognoser-2280.csv')
})

// Revideringarna mellan cirkulären (#161). Budgetåret är nästa kalenderår, så klockan låses till hösten 2026.
const revidering = async (page: import('@playwright/test').Page) => {
  await page.clock.setFixedTime(new Date('2026-11-26T12:00:00+01:00'))
  await page.goto('/ekonomi/skatteunderlag')
}

test('värmekartan visar ändringen mot föregående cirkulär per år som en tabell', async ({ page }) => {
  await revidering(page)
  const sektion = page.getByTestId('revideringar')
  const karta = sektion.getByRole('table', { name: /Ändring av summa intäkter inklusive avräkning/ })
  await expect(karta).toBeVisible()
  // Värmekartan ligger ovanför linjediagrammet.
  const yKarta = (await sektion.boundingBox())!.y
  expect(yKarta).toBeLessThan((await page.getByTestId('prognosdiagram').boundingBox())!.y)

  // Bara cirkulär från 2026 finns, så 26:12 har inget föregående cirkulär: fyra rader, åtta prognosår.
  await expect(karta.getByRole('rowheader')).toHaveCount(4)
  await expect(karta.getByRole('columnheader')).toHaveCount(9)
  await expect(karta.getByRole('rowheader').first()).toContainText('26:12 → 26:18')

  const cell = (rad: string, ar: number) => karta.locator(`tr[data-revidering="${rad}"] td[data-ar="${ar}"]`)
  // 26:12 → 26:18 sänkte 2026 med 15,8 mnkr (slutavräkningarna) och höjde 2027 med 10,1 mnkr.
  await expect(cell('26:12 → 26:18', 2026)).toContainText('−15,8 mnkr')
  await expect(cell('26:12 → 26:18', 2027)).toContainText('+10,1 mnkr')
  await expect(cell('26:18 → 26:24', 2026)).toContainText('0,0 mnkr')
  await expect(cell('26:18 → 26:24', 2026)).not.toContainText('−')
  await expect(cell('26:27 → 26:28', 2033)).toContainText('−4,2 mnkr')

  // Färgen följer tecknet: blå för höjning, röd för sänkning, ytans färg för ingen ändring.
  const bakgrund = (l: import('@playwright/test').Locator) => l.evaluate((e) => getComputedStyle(e).backgroundColor)
  const yta = await sektion.evaluate((e) => getComputedStyle(e).backgroundColor)
  expect(await bakgrund(cell('26:18 → 26:24', 2026))).toBe(yta)
  const lagre = await bakgrund(cell('26:12 → 26:18', 2026))
  const hogre = await bakgrund(cell('26:12 → 26:18', 2027))
  expect(lagre).not.toBe(yta)
  expect(hogre).not.toBe(yta)
  expect(lagre).not.toBe(hogre)

  // Procent i verktygstipset.
  await cell('26:12 → 26:18', 2026).hover()
  const tips = sektion.getByTestId('revideringstips')
  await expect(tips).toContainText('2026, 26:12 → 26:18')
  await expect(tips).toContainText(/−15,8 mnkr \(−0,7\d %\)/)
  await expect(tips).toContainText('SKR')
})

test('raden om budgeten räknar budgetåret från årets första cirkulär till det senaste', async ({ page }) => {
  await revidering(page)
  await expect(page.getByTestId('budgetrad')).toHaveText(
    'Prognosen för 2027 har höjts med 15,0 mnkr sedan februari (26:12 → 26:28).',
  )
})

test('drivkrafterna har budgetåret och de två senaste cirkulären förvalda och summan stämmer med värmekartan', async ({ page }) => {
  await revidering(page)
  const d = page.getByTestId('drivkrafter')
  await expect(d.getByTestId('drivkraft-ar')).toHaveValue('2027')
  await expect(d.getByTestId('drivkraft-fran')).toHaveValue('26:27')
  await expect(d.getByTestId('drivkraft-till')).toHaveValue('26:28')

  const stapel = (rad: string) => d.locator(`[data-testid="drivkraft"][data-rad="${rad}"]`)
  await expect(stapel('skatteintakter')).toContainText('Skatteintäkter')
  await expect(stapel('skatteintakter')).toContainText('+4,2 mnkr')
  await expect(stapel('slutavrakning_2027')).toContainText('−3,5 mnkr')
  // Rader utan ändring och summaraderna visas inte.
  await expect(stapel('fastighetsavgift')).toHaveCount(0)
  await expect(stapel('summa_intakter')).toHaveCount(0)
  await expect(stapel('summa_inkl')).toHaveCount(0)

  const karta = page.getByTestId('revideringskarta')
  const ruta = karta.locator('tr[data-revidering="26:27 → 26:28"] td[data-ar="2027"]')
  await expect(ruta).toContainText('+1,8 mnkr')
  await expect(d.getByTestId('drivkraftssumma')).toContainText('+1,8 mnkr')
  await expect(ruta).toHaveClass(/vald/)

  // Byt år och cirkulär: 26:12 → 26:18 för 2026 drevs av slutavräkningarna.
  await d.getByTestId('drivkraft-ar').selectOption('2026')
  await d.getByTestId('drivkraft-fran').selectOption('26:12')
  await d.getByTestId('drivkraft-till').selectOption('26:18')
  await expect(d.getByTestId('drivkraft')).toHaveCount(2)
  await expect(stapel('slutavrakning_2026')).toContainText('−11,6 mnkr')
  await expect(stapel('slutavrakning_korrigering')).toBeVisible()
  await expect(d.getByTestId('drivkraftssumma')).toContainText('−15,8 mnkr')

  // En ruta i värmekartan väljer år och cirkulär i drivkrafterna.
  await karta.locator('tr[data-revidering="26:24 → 26:27"] td[data-ar="2030"]').click()
  await expect(d.getByTestId('drivkraft-ar')).toHaveValue('2030')
  await expect(d.getByTestId('drivkraft-fran')).toHaveValue('26:24')
  await expect(d.getByTestId('drivkraft-till')).toHaveValue('26:27')
  await expect(d.getByTestId('drivkraftssumma')).toContainText('−4,0 mnkr')
})

test('värmekartan har en egen CSV med ändringen per cirkulär och år', async ({ page }) => {
  await revidering(page)
  const nedladdning = page.waitForEvent('download')
  await page.getByTestId('exportera-revideringar').click()
  const fil = await nedladdning
  expect(fil.suggestedFilename()).toBe('skatteunderlagsprognos-revideringar-2026.csv')
  const text = (await import('node:fs')).readFileSync((await fil.path())!, 'utf8')
  const rader = text.replace(/^﻿/, '').split('\n')
  expect(rader[0]).toBe('Från cirkulär;Till cirkulär;Publicerad;Rad;År;Ändring tkr;Ändring procent;Källa')
  expect(rader).toHaveLength(1 + 4 * 8)
  expect(rader.find((r) => r.startsWith('26:12;26:18;2026-04-29;summa_inkl;2026;'))).toMatch(/;-15\d{3}\.\d{3};-0\.7\d{3};https:/)
})
