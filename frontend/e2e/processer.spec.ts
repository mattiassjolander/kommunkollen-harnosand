import { expect, test } from '@playwright/test'
import { API_PORT } from '../playwright.config'

// Processer ur reglementen och delegationsordningar (#152): en redaktör lägger till en process och läser in stegen, en
// utgivare som inte gjort det granskar och publicerar processen, och läsaren ser den på processidan, på dokumentsidan
// och i listan. Stegen är testdata med citat ur det inspelade attestreglementet (STYRANDE_URVAL=1).

const api = `http://127.0.0.1:${API_PORT}`
const ATTEST = '18.580e43d7163221b2781b73fc'
const STEG = {
  processer: [
    {
      process: 'Attest av ekonomiska transaktioner',
      steg: [
        {
          vem: 'Attestanten',
          vad: 'Intygar att kontroll har genomförts.',
          nar: 'Innan transaktionen bokförs',
          kalla: {
            dokument: ATTEST,
            sida: 3,
            paragraf: '1 Reglementets omfattning',
            text: 'Attestreglementet gäller för kommunens samtliga interna och externa ekonomiska transaktioner.',
          },
        },
      ],
    },
  ],
}

test.beforeAll(async ({ request }) => {
  test.setTimeout(120_000)
  expect((await request.post(`${api}/api/auth/test/redaktor`)).ok()).toBeTruthy()
  expect((await request.post(`${api}/api/insamlingar?kalla=harnosand-styrande-dokument`)).ok()).toBeTruthy()
})

test('en redaktör lägger till en process, en utgivare publicerar den och läsaren ser stegen märkta Analys', async ({
  page,
}) => {
  // Redaktören lägger till processen på listan. Den första listan finns redan.
  await page.request.post('/api/auth/test/redaktor')
  await page.goto('/redaktion/processer')
  await expect(page.getByRole('heading', { name: 'Processer', level: 1 })).toBeVisible()
  await expect(page.getByTestId('processforslag').filter({ hasText: 'Kallelse till sammanträde' })).toHaveCount(1)
  await page.getByTestId('ny-namn').fill('Attest av ekonomiska transaktioner')
  await page.getByRole('button', { name: 'Lägg till' }).click()
  const forslag = page.getByTestId('processforslag').filter({ hasText: 'Attest av ekonomiska transaktioner' })
  await expect(forslag.getByTestId('inga-steg')).toBeVisible()

  // Skillens steg läses in som utkast.
  const svar = await page.request.post('/api/processer/inlasning', { data: STEG })
  expect(svar.ok(), await svar.text()).toBeTruthy()

  // Utkastet syns inte för läsaren.
  await page.request.post('/api/auth/logga-ut')
  await page.goto('/politik/styrande-dokument/processer')
  await expect(page.getByTestId('processrad').filter({ hasText: 'Attest av ekonomiska transaktioner' })).toHaveCount(0)

  // En utgivare som inte lagt till processen granskar och publicerar den.
  await page.request.post('/api/auth/test/utgivare')
  await page.goto('/redaktion/processer')
  await expect(forslag).toContainText('Tillagd av test-redaktor@kommunkollen.test')
  await expect(forslag.getByTestId('steg')).toHaveCount(1)
  await forslag.getByTestId('granska').click()
  await expect(forslag.getByTestId('granskning')).toContainText('Granskad')
  await forslag.getByTestId('publicera').click()
  await expect(forslag.getByTestId('granskning')).toContainText('Publicerad')

  // Läsaren: listan, dokumentsidan och processidan.
  await page.request.post('/api/auth/logga-ut')
  await page.goto('/politik/styrande-dokument?giltighet=alla')
  const rad = page.getByTestId('styrdokument').filter({ hasText: 'Attestreglemente' })
  await expect(rad.getByTestId('antal-processer')).toHaveText('1 Analys')
  await rad.getByRole('link', { name: 'Attestreglemente' }).click()
  const avsnitt = page.getByTestId('processer')
  await expect(avsnitt.getByTestId('process')).toHaveText('Attest av ekonomiska transaktioner · 1 steg ur dokumentet')
  await avsnitt.getByRole('link', { name: 'Attest av ekonomiska transaktioner' }).click()

  await expect(page.getByRole('heading', { name: 'Attest av ekonomiska transaktioner', level: 1 })).toBeVisible()
  const process = page.getByTestId('process')
  await expect(process).toContainText('Analys')
  await expect(process).toHaveCSS('border-top-style', 'dashed')
  const steg = process.getByTestId('steg')
  await expect(steg.getByTestId('vem')).toHaveText('Attestanten')
  await expect(steg.getByTestId('nar')).toHaveText('Innan transaktionen bokförs')
  await expect(steg.getByTestId('citat')).toContainText('”Attestreglementet gäller för kommunens samtliga')
  await expect(steg.getByTestId('kalla')).toContainText('Attestreglemente, version 1, 1 Reglementets omfattning, s. 3')
  expect(await steg.getByRole('link', { name: 'Sidan i PDF:en' }).getAttribute('href')).toMatch(
    /^\/api\/styrande-dokument\/\d+\/versioner\/1#page=3$/,
  )

  await page.getByRole('link', { name: '‹ Processer' }).click()
  await expect(page.getByTestId('processrad').filter({ hasText: 'Attest av ekonomiska transaktioner' })).toContainText(
    '1 steg',
  )
})
