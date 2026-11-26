import { expect, test } from '@playwright/test'

// Sidomenyn (#175): 248 px bred från 1280 px skärmbredd och 220 px under, så att ingen menypost bryts.

test('sidomenyn är bredare på stor skärm och "Kommunen i jämförelse" ryms på en rad', async ({ page }) => {
  await page.setViewportSize({ width: 1440, height: 900 })
  await page.goto('/')
  const sidomeny = page.locator('#navigering')
  await expect(sidomeny).toBeVisible()
  expect((await sidomeny.boundingBox())?.width).toBe(248)

  const nav = page.getByRole('navigation', { name: 'Huvudvyer' })
  const jamforelse = nav.getByRole('link', { name: 'Kommunen i jämförelse' })
  const oversikt = nav.getByRole('link', { name: 'Översikt' })
  // Posten har samma höjd som en post med ett kort namn, alltså en rad.
  const hojd = (await jamforelse.boundingBox())!.height
  expect(hojd).toBe((await oversikt.boundingBox())!.height)

  // Utfälld och vald står posten i fetstil, och den ryms fortfarande på en rad.
  await jamforelse.click()
  await expect(nav.getByRole('button', { name: 'Undervyer till Kommunen i jämförelse' })).toHaveAttribute(
    'aria-expanded',
    'true',
  )
  await expect(jamforelse).toHaveCSS('font-weight', '600')
  // Inter i fetstil laddas först när fet text visas. Vänta på typsnittet innan posten mäts.
  await page.evaluate(() => document.fonts.load('600 14px Inter'))
  await expect.poll(async () => (await jamforelse.boundingBox())!.height).toBe(hojd)
  // Pilen bredvid står kvar inne i menyn.
  const pil = (await nav.getByRole('button', { name: 'Undervyer till Kommunen i jämförelse' }).boundingBox())!
  expect(pil.x + pil.width).toBeLessThanOrEqual(248)

  // Under 1280 px är menyn kvar på 220 px.
  await page.setViewportSize({ width: 1200, height: 900 })
  await expect.poll(async () => (await sidomeny.boundingBox())?.width).toBe(220)
})
