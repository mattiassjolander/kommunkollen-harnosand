import { expect, test } from '@playwright/test'

test('knappen byter mellan ljust och mörkt läge och valet sparas', async ({ page }) => {
  await page.emulateMedia({ colorScheme: 'light' })
  await page.goto('/')
  const knapp = page.getByTestId('temavaljare')
  const html = page.locator('html')
  const bakgrund = () => page.evaluate(() => getComputedStyle(document.body).backgroundColor)

  // Utan eget val följer sidan systemet.
  await expect(knapp).toHaveAttribute('data-tema', 'ljust')
  await expect(knapp).toHaveAccessibleName('Byt till mörkt läge')
  const ljus = await bakgrund()

  await knapp.click()
  await expect(knapp).toHaveAttribute('data-tema', 'morkt')
  await expect(knapp).toHaveAccessibleName('Byt till ljust läge')
  await expect(html).toHaveAttribute('data-theme', 'dark')
  expect(await bakgrund()).not.toBe(ljus)

  // Valet sparas och gäller efter omladdning, även när systemet är ljust.
  await page.reload()
  await expect(html).toHaveAttribute('data-theme', 'dark')
  await expect(page.getByTestId('temavaljare')).toHaveAttribute('data-tema', 'morkt')

  await page.getByTestId('temavaljare').click()
  await expect(html).toHaveAttribute('data-theme', 'light')
  expect(await bakgrund()).toBe(ljus)
})

test('utan eget val följer sidan systemets mörka läge', async ({ page }) => {
  await page.emulateMedia({ colorScheme: 'dark' })
  await page.goto('/')
  await expect(page.getByTestId('temavaljare')).toHaveAttribute('data-tema', 'morkt')
  await expect(page.locator('html')).not.toHaveAttribute('data-theme', /.+/)
})
