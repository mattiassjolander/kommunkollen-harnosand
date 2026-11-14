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
  await page.locator('path[data-flode="omrade_590"]').click()
  await expect(page.getByTestId('flodesdetalj')).toContainText('Vård och omsorg')
  await expect(page.getByTestId('flodesdetalj')).toContainText('· 2019 ·')

  // Tabellvyn listar samma flöden.
  await page.getByText('Visa flödena som tabell').click()
  await expect(page.getByTestId('flodestabell').getByRole('row', { name: /Kommunalskatt/ })).toBeVisible()
})
