import { expect, test, type Page } from '@playwright/test'

// Högtidsteman i gränssnittet (issue #70). Datumet styrs med Playwrights klocka.

async function oppnaDen(page: Page, iso: string, sokvag = '/') {
  await page.clock.setFixedTime(new Date(iso))
  await page.goto(sokvag)
  await expect(page.getByTestId('statusindikator')).toBeVisible()
}

function luminans(rgb: string): number {
  const [r, g, b] = rgb.match(/\d+(\.\d+)?/g)!.slice(0, 3).map((v) => {
    const c = Number(v) / 255
    return c <= 0.03928 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4
  })
  return 0.2126 * r + 0.7152 * g + 0.0722 * b
}

function kontrast(a: string, b: string): number {
  const [l1, l2] = [luminans(a), luminans(b)].sort((x, y) => y - x)
  return (l1 + 0.05) / (l2 + 0.05)
}

/** Färger som temat aldrig får ändra (accent, navigering, partier, diagram, status). */
async function skyddadeFarger(page: Page) {
  return page.evaluate(() => {
    const s = getComputedStyle(document.documentElement)
    const namn = [
      '--accent',
      '--accent-wash',
      '--nav',
      '--sidhuvud',
      '--sidhuvud-ink',
      '--parti-s',
      '--parti-m',
      '--parti-sd',
      '--parti-c',
      '--parti-v',
      '--parti-kd',
      '--parti-l',
      '--parti-mp',
      '--series-1',
      '--series-8',
      '--status-good',
      '--status-warning',
      '--status-critical',
    ]
    return {
      tokens: Object.fromEntries(namn.map((n) => [n, s.getPropertyValue(n).trim()])),
      nav: getComputedStyle(document.querySelector('.nav')!).backgroundColor,
    }
  })
}

for (const lage of ['light', 'dark'] as const) {
  test(`jul: stjärnan vid logotypen och "God jul" i sidhuvudet, ${lage === 'light' ? 'ljust' : 'mörkt'} läge`, async ({
    page,
  }) => {
    await page.emulateMedia({ colorScheme: lage, reducedMotion: 'reduce' })
    await oppnaDen(page, '2026-11-24T12:00:00+01:00')
    await expect(page.getByTestId('hogtidsrad')).toHaveCount(0)
    await expect(page.getByTestId('hogtidssymbol')).toHaveCount(0)
    const fore = await skyddadeFarger(page)

    await oppnaDen(page, '2026-12-24T08:00:00+01:00')
    const rad = page.getByTestId('hogtidsrad')
    await expect(rad).toHaveText('God jul')
    await expect(rad).toHaveAttribute('data-tema', 'jul')
    const symbol = page.getByTestId('hogtidssymbol')
    await expect(symbol).toHaveAttribute('data-symbol', 'stjarnan')
    await expect(symbol).toHaveAttribute('aria-hidden', 'true')

    // Symbolen är högst 24 px.
    const ruta = (await symbol.boundingBox())!
    expect(ruta.width).toBeLessThanOrEqual(24)
    expect(ruta.height).toBeLessThanOrEqual(24)

    // Inget annat ändras av temat.
    expect(await skyddadeFarger(page)).toEqual(fore)

    // Kontrast: raden mot sidhuvudet (text, 4,5:1) och symbolen mot navigeringen (grafik, 3:1).
    const farger = await page.evaluate(() => {
      const rad = document.querySelector('[data-testid="hogtidsrad"]')!
      const ikon = document.querySelector('[data-testid="hogtidssymbol"] .ikon')!
      return {
        text: getComputedStyle(rad).color,
        sidhuvud: getComputedStyle(document.querySelector('.sidhuvud')!).backgroundColor,
        ikon: getComputedStyle(ikon).backgroundColor,
        nav: getComputedStyle(document.querySelector('.nav')!).backgroundColor,
        animationer: document.getAnimations().length,
      }
    })
    expect(kontrast(farger.text, farger.sidhuvud)).toBeGreaterThanOrEqual(4.5)
    expect(kontrast(farger.ikon, farger.nav)).toBeGreaterThanOrEqual(3)
    expect(farger.animationer).toBe(0)

    await page.screenshot({ path: `test-results/hogtid-jul-${lage}.png` })

    // Annandag jul är sista dagen.
    await oppnaDen(page, '2026-12-27T08:00:00+01:00')
    await expect(page.getByTestId('hogtidsrad')).toHaveCount(0)
  })
}

test('Härnösands dag: antal år och källan i en tooltip', async ({ page }) => {
  await oppnaDen(page, '2026-03-11T09:00:00+01:00')
  const text = page.getByTestId('hogtidsrad-text')
  await expect(text).toContainText('Härnösand fick sina stadsprivilegier i dag för 441 år sedan (1585)')
  await expect(page.getByTestId('hogtidssymbol')).toHaveAttribute('data-symbol', 'vagen')
  const kalla = page.getByTestId('hogtidsrad-kalla')
  await expect(kalla).toBeHidden()
  await text.focus()
  await expect(kalla).toBeVisible()
  await expect(kalla).toHaveText(
    'Den 11 mars 1585 fick Härnösand sina stadsprivilegier av Johan III. Det är den dag som brukar firas.',
  )
  await expect(text).toHaveAccessibleDescription(/Johan III/)
})

test('nedräkningen till Härnösands dag visas utan symbol', async ({ page }) => {
  await oppnaDen(page, '2026-03-01T09:00:00+01:00')
  await expect(page.getByTestId('hogtidsrad')).toHaveText(
    '10 dagar kvar till Härnösands dag – 441 år sedan stadsprivilegierna',
  )
  await expect(page.getByTestId('hogtidssymbol')).toHaveCount(0)
})

test('valdagen länkar till val.se', async ({ page }) => {
  await oppnaDen(page, '2026-09-13T09:00:00+02:00')
  const rad = page.getByTestId('hogtidsrad')
  await expect(rad).toContainText('I dag är det val')
  await expect(rad.getByRole('link', { name: 'val.se' })).toHaveAttribute('href', 'https://www.val.se/')
  await expect(page.getByTestId('hogtidssymbol')).toHaveAttribute('data-symbol', 'valsedel')
})

test('"Visa inte teman" stänger av temat och valet sparas', async ({ page }) => {
  await oppnaDen(page, '2026-12-25T10:00:00+01:00')
  await expect(page.getByTestId('hogtidsrad')).toHaveText('God jul')
  const knapp = page.getByTestId('visa-teman')
  await expect(knapp).toHaveText('Visa inte teman')
  await knapp.click()
  await expect(page.getByTestId('hogtidsrad')).toHaveCount(0)
  await expect(page.getByTestId('hogtidssymbol')).toHaveCount(0)
  await expect(knapp).toHaveText('Visa teman')

  await page.reload()
  await expect(page.getByTestId('statusindikator')).toBeVisible()
  await expect(page.getByTestId('visa-teman')).toHaveText('Visa teman')
  await expect(page.getByTestId('hogtidsrad')).toHaveCount(0)

  // Förhandsvisning gäller ändå.
  await page.goto('/?tema=lucia')
  await expect(page.getByTestId('hogtidsrad')).toHaveText('Glad lucia')

  await page.goto('/')
  await page.getByTestId('visa-teman').click()
  await expect(page.getByTestId('hogtidsrad')).toHaveText('God jul')
})

test('?tema= förhandsvisar ett tema oavsett datum och ?tema=inget stänger av', async ({ page }) => {
  await oppnaDen(page, '2026-11-24T12:00:00+01:00', '/?tema=jul')
  await expect(page.getByTestId('hogtidsrad')).toHaveText('God jul')
  await expect(page.getByTestId('hogtidssymbol')).toHaveAttribute('data-symbol', 'stjarnan')

  const forvantat: Record<string, [string, string | null]> = {
    nyar: ['Gott nytt år', 'gnistor'],
    pask: ['Glad påsk', 'agg'],
    nationaldagen: ['Sveriges nationaldag', 'flagga'],
    midsommar: ['Glad midsommar', 'blomkrans'],
    lucia: ['Glad lucia', 'ljus'],
  }
  for (const [namn, [text, symbol]] of Object.entries(forvantat)) {
    await page.goto(`/?tema=${namn}`)
    await expect(page.getByTestId('hogtidsrad')).toHaveText(text)
    await expect(page.getByTestId('hogtidssymbol')).toHaveAttribute('data-symbol', symbol!)
  }

  await page.goto('/?tema=nedrakning&datum=2026-03-01')
  await expect(page.getByTestId('hogtidsrad')).toHaveText(
    '10 dagar kvar till Härnösands dag – 441 år sedan stadsprivilegierna',
  )

  await page.clock.setFixedTime(new Date('2026-12-24T10:00:00+01:00'))
  await page.goto('/?tema=inget')
  await expect(page.getByTestId('statusindikator')).toBeVisible()
  await expect(page.getByTestId('hogtidsrad')).toHaveCount(0)
  await expect(page.getByTestId('hogtidssymbol')).toHaveCount(0)
})

test('symbolerna i mörkt läge håller kontrasten mot navigeringen', async ({ page }) => {
  await page.emulateMedia({ colorScheme: 'dark' })
  for (const namn of ['nyar', 'pask', 'midsommar', 'valdagen', 'lucia', 'harnosandsdag']) {
    await page.goto(`/?tema=${namn}`)
    await expect(page.getByTestId('hogtidssymbol')).toBeVisible()
    const [linje, nav] = await page.evaluate(() => {
      const el = document.querySelector('[data-testid="hogtidssymbol"] .linje, [data-testid="hogtidssymbol"] .ikon')!
      const s = getComputedStyle(el)
      return [
        el.classList.contains('ikon') ? s.backgroundColor : s.stroke,
        getComputedStyle(document.querySelector('.nav')!).backgroundColor,
      ]
    })
    expect(kontrast(linje, nav), namn).toBeGreaterThanOrEqual(3)
  }
})
