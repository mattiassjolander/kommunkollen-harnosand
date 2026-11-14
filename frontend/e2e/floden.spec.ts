import { expect, test } from '@playwright/test'
import { API_PORT } from '../playwright.config'

test.beforeAll(async ({ request }) => {
  const api = `http://127.0.0.1:${API_PORT}`
  expect((await request.post(`${api}/api/auth/test/redaktor`)).ok()).toBeTruthy()
  expect((await request.post(`${api}/api/insamlingar`)).ok()).toBeTruthy()
})

test('Sankey renderar och ett klick på ett flöde visar belopp, andel och källa', async ({ page }) => {
  await page.goto('/ekonomi')
  await page.getByRole('navigation', { name: 'Huvudvyer' }).getByRole('link', { name: 'Ekonomiska flöden' }).click()
  await expect(page.getByRole('heading', { name: 'Ekonomiska flöden' })).toBeVisible()

  // Diagrammet anger flödestyp och indelning.
  const info = page.getByTestId('flodesinfo')
  await expect(info).toContainText('Bruttoflöden')
  await expect(info).toContainText('inte kommunens nämnder')

  // Senaste år med fullständigt underlag är förvalt.
  await expect(page.getByTestId('ar')).toHaveValue('2025')
  const skatt = page.locator('path[data-flode="kommunalskatt"]')
  await expect(skatt).toBeVisible()
  await expect(page.locator('path[data-flode="omrade_490"]')).toBeVisible()

  await skatt.click()
  const detalj = page.getByTestId('flodesdetalj')
  await expect(detalj.getByRole('heading')).toContainText('Kommunalskatt → Kommunens intäkter')
  await expect(detalj.getByTestId('belopp')).toContainText('mnkr')
  await expect(detalj).toContainText('Andel av totalen')
  await expect(detalj).toContainText(/Per invånare[\d\s ]+ kr/)
  await expect(detalj.getByRole('link', { name: /SCB, räkenskapssammandraget, tabell ResultKnN/ })).toHaveAttribute(
    'href',
    /statistikdatabasen\.scb\.se/,
  )
})

test('ett annat år kan väljas och valet speglas i URL:en', async ({ page }) => {
  await page.goto('/floden')
  await page.getByTestId('ar').selectOption('2019')
  await expect(page).toHaveURL(/ar=2019/)
  await expect(page.getByTestId('flodesdetalj')).toContainText('31 december 2019') // året har laddats
  await page.locator('path[data-flode="omrade_590"]').click()
  await expect(page.getByTestId('flodesdetalj')).toContainText('Vård och omsorg')
  await expect(page.getByTestId('flodesdetalj')).toContainText('· 2019 ·')

  // Tabellvyn listar samma flöden.
  await page.getByText('Visa flödena som tabell').click()
  await expect(page.getByTestId('flodestabell').getByRole('row', { name: /Kommunalskatt/ })).toBeVisible()
})

test('ett verksamhetsområde kan fördjupas i kostnadsslag och man kan gå tillbaka', async ({ page }) => {
  await page.goto('/floden?ar=2024')
  await page.locator('[data-fordjupa="omrade_490"]').click()
  await expect(page).toHaveURL(/verksamhet=490/)
  await expect(page).toHaveURL(/ar=2024/)
  await expect(page.getByTestId('detaljniva')).toContainText('Kommunnivå › Pedagogisk verksamhet')
  await expect(page.getByRole('heading', { name: 'Pedagogisk verksamhet: kostnadsslag' })).toBeVisible()
  for (const slag of ['personal', 'lokaler', 'kop_av_tjanster', 'material', 'kapitalkostnader', 'ovrigt'])
    await expect(page.locator(`path[data-flode="${slag}"]`)).toBeVisible()

  await page.locator('path[data-flode="personal"]').click()
  const detalj = page.getByTestId('flodesdetalj')
  await expect(detalj.getByRole('heading')).toContainText('Pedagogisk verksamhet, bruttokostnad → Personal')
  await expect(detalj.getByRole('link', { name: /tabell Driftredovisning/ })).toBeVisible()

  await page.getByTestId('till-kommunniva').click()
  await expect(page).not.toHaveURL(/verksamhet=/)
  await expect(page.locator('path[data-flode="kommunalskatt"]')).toBeVisible()

  // Fördjupningen nås också från detaljrutan för ett områdesflöde.
  await page.locator('path[data-flode="omrade_590"]').click()
  await page.getByTestId('visa-kostnadsslag').click()
  await expect(page.getByTestId('detaljniva')).toContainText('Vård och omsorg')
})

test('två år kan jämföras och förändringen visas i kronor och procent', async ({ page }) => {
  await page.goto('/floden?ar=2024')
  await page.getByTestId('jamfor').selectOption('2023')
  await expect(page).toHaveURL(/jamfor=2023/)
  await expect(page.getByTestId('nodforandring').first()).toBeVisible()

  await page.locator('path[data-flode="kommunalskatt"]').click()
  const forandring = page.getByTestId('flodesdetalj').getByTestId('forandring')
  await expect(forandring).toContainText(/[+−]\d[\d ]*,\d mnkr/)
  await expect(page.getByTestId('forandring-procent')).toContainText(/^([+−]\d+,\d|0,0) %$/)

  await page.getByText('Visa flödena som tabell').click()
  await expect(page.getByTestId('flodestabell').getByRole('columnheader', { name: 'Förändring, %' })).toBeVisible()

  // Ett ofullständigt år jämförs inte, och det sägs ut.
  await page.getByTestId('jamfor').selectOption('2005')
  await expect(page.getByTestId('jamforelse-saknas')).toBeVisible()
})

test('detaljnivå och jämförelseår återställs från URL:en', async ({ page }) => {
  await page.goto('/floden?ar=2024&jamfor=2023&verksamhet=590')
  await expect(page.getByRole('heading', { name: 'Vård och omsorg: kostnadsslag' })).toBeVisible()
  await expect(page.getByTestId('ar')).toHaveValue('2024')
  await expect(page.getByTestId('jamfor')).toHaveValue('2023')
  await expect(page.getByTestId('nodforandring').first()).toBeVisible()
})
