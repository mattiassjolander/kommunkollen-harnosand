import { createApp } from 'vue'
import { createRouter, createWebHistory, type RouteRecordRaw } from 'vue-router'
import '@fontsource/inter/400.css'
import '@fontsource/inter/600.css'
import './styles/tokens.css'
import App from './App.vue'
import { dokumenttitel, FLYTTADE } from './navigering'
import DatakallorView from './views/DatakallorView.vue'
import EkonomiView from './views/EkonomiView.vue'
import SkatteunderlagView from './views/SkatteunderlagView.vue'
import UndersokningarView from './views/UndersokningarView.vue'
import RankningarView from './views/RankningarView.vue'
import RankningView from './views/RankningView.vue'
import BudgetOchUtfallView from './views/BudgetOchUtfallView.vue'
import FlodenView from './views/FlodenView.vue'
import KommandeView from './views/KommandeView.vue'
import OversiktView from './views/OversiktView.vue'
import SokView from './views/SokView.vue'
import ArendeView from './views/politik/ArendeView.vue'
import AvvikelserView from './views/politik/AvvikelserView.vue'
import BudgetforslagView from './views/politik/BudgetforslagView.vue'
import TidigareBudgetView from './views/politik/TidigareBudgetView.vue'
import BudgetforslagetView from './views/politik/BudgetforslagetView.vue'
import BudgetutkastView from './views/politik/BudgetutkastView.vue'
import BehandlingView from './views/politik/BehandlingView.vue'
import KopplingarView from './views/politik/KopplingarView.vue'
import NamnvarianterView from './views/politik/NamnvarianterView.vue'
import SammantradesplanerView from './views/politik/SammantradesplanerView.vue'
import KalenderView from './views/KalenderView.vue'
import LedamotView from './views/politik/LedamotView.vue'
import LedamoterView from './views/politik/LedamoterView.vue'
import StyrandeDokumentView from './views/politik/StyrandeDokumentView.vue'
import StyrdokumentView from './views/politik/StyrdokumentView.vue'
import MotstridigheterView from './views/politik/MotstridigheterView.vue'
import MotstridighetsforslagView from './views/politik/MotstridighetsforslagView.vue'
import ProcesserView from './views/politik/ProcesserView.vue'
import ProcessView from './views/politik/ProcessView.vue'
import ProcessforslagView from './views/politik/ProcessforslagView.vue'
import PolitikView from './views/politik/PolitikView.vue'
import ProtokollavvikelserView from './views/politik/ProtokollavvikelserView.vue'
import RattelserView from './views/politik/RattelserView.vue'
import PartitillhorighetView from './views/politik/PartitillhorighetView.vue'
import StatistikView from './views/politik/StatistikView.vue'
import TopplistorView from './views/politik/TopplistorView.vue'
import SammantradeView from './views/politik/SammantradeView.vue'
import SammansattningView from './views/politik/SammansattningView.vue'

const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/', component: OversiktView, meta: { titel: 'Översikt' } },
    { path: '/ekonomi', component: EkonomiView, meta: { titel: 'Nyckeltal' } },
    { path: '/ekonomi/skatteunderlag', component: SkatteunderlagView, meta: { titel: 'Skatteunderlagsprognos' } },
    { path: '/ekonomi/budget-och-utfall', component: BudgetOchUtfallView, meta: { titel: 'Budget och utfall' } },
    { path: '/ekonomi/floden', component: FlodenView, meta: { titel: 'Ekonomiska flöden' } },
    { path: '/undersokningar', component: UndersokningarView, meta: { titel: 'Undersökningar' } },
    { path: '/rankningar', component: RankningarView, meta: { titel: 'Rankningar' } },
    { path: '/rankningar/:id', component: RankningView, meta: { titel: 'Rankning' } },
    // Grupperna Kommunen i jämförelse och Om Kommunkollen har ingen egen sida och leder till första undervyn.
    { path: '/jamforelse', redirect: '/rankningar' },
    { path: '/om', redirect: '/datakallor' },
    { path: '/politik', component: PolitikView, meta: { titel: 'Sammanträden' } },
    { path: '/politik/kommande', component: KommandeView, meta: { titel: 'Kommande ärenden' } },
    { path: '/politik/kalender', component: KalenderView, meta: { titel: 'Kalender' } },
    { path: '/politik/sammantraden/:id', component: SammantradeView, meta: { titel: 'Sammanträde' } },
    {
      path: '/politik/sammantraden/:id/paragraf/:paragraf',
      component: BehandlingView,
      meta: { titel: 'Behandling' },
    },
    { path: '/politik/arenden/:id', component: ArendeView, meta: { titel: 'Ärende' } },
    { path: '/redaktion/kopplingar', component: KopplingarView, meta: { titel: 'Kopplingar' } },
    { path: '/redaktion/namnvarianter', component: NamnvarianterView, meta: { titel: 'Namnvarianter' } },
    { path: '/redaktion/sammantradesplaner', component: SammantradesplanerView, meta: { titel: 'Sammanträdesplaner' } },
    { path: '/redaktion/rattelser', component: RattelserView, meta: { titel: 'Rättelser' } },
    { path: '/redaktion/partitillhorighet', component: PartitillhorighetView, meta: { titel: 'Partitillhörighet' } },
    { path: '/politik/statistik', component: StatistikView, meta: { titel: 'Statistik' } },
    { path: '/politik/topplistor', component: TopplistorView, meta: { titel: 'Topplistor' } },
    { path: '/politik/avvikelser', component: AvvikelserView, meta: { titel: 'Avvikelser i protokollen' } },
    { path: '/redaktion/att-anmala', component: ProtokollavvikelserView, meta: { titel: 'Att anmäla' } },
    { path: '/politik/budget', component: BudgetforslagView, meta: { titel: 'Budgetförslag' } },
    {
      path: '/politik/budget/tidigare/:slag(forslag|planforutsattningar)/:id(\\d+)',
      component: TidigareBudgetView,
      meta: { titel: 'Förra versionen' },
    },
    { path: '/politik/budget/:ar(\\d{4})/:nyckel', component: BudgetforslagetView, meta: { titel: 'Budgetförslag' } },
    { path: '/redaktion/budgetutkast', component: BudgetutkastView, meta: { titel: 'Budgetutkast' } },
    { path: '/politik/ledamoter', component: LedamoterView, meta: { titel: 'Ledamöter' } },
    { path: '/politik/ledamoter/:id', component: LedamotView, meta: { titel: 'Ledamot' } },
    { path: '/politik/sammansattning', component: SammansattningView, meta: { titel: 'Sammansättning' } },
    { path: '/politik/styrande-dokument', component: StyrandeDokumentView, meta: { titel: 'Styrande dokument' } },
    { path: '/politik/styrande-dokument/:id(\\d+)', component: StyrdokumentView, meta: { titel: 'Styrande dokument' } },
    {
      path: '/politik/styrande-dokument/motstridigheter',
      component: MotstridigheterView,
      meta: { titel: 'Motstridigheter' },
    },
    { path: '/redaktion/motstridigheter', component: MotstridighetsforslagView, meta: { titel: 'Motstridigheter' } },
    { path: '/politik/styrande-dokument/processer', component: ProcesserView, meta: { titel: 'Processer' } },
    {
      path: '/politik/styrande-dokument/processer/:id(\\d+)',
      component: ProcessView,
      meta: { titel: 'Processer' },
    },
    { path: '/redaktion/processer', component: ProcessforslagView, meta: { titel: 'Processer' } },
    { path: '/redaktion', redirect: '/redaktion/rattelser' },
    // Vyer som har bytt adress (#146, #160).
    ...Object.entries(FLYTTADE).map(
      ([fran, till]): RouteRecordRaw => ({ path: fran, redirect: (to) => ({ path: till, query: to.query, hash: to.hash }) }),
    ),
    { path: '/datakallor', component: DatakallorView, meta: { titel: 'Datakällor' } },
    { path: '/sok', component: SokView, meta: { titel: 'Sök' } },
  ],
})

router.afterEach((to) => {
  document.title = dokumenttitel(to.path, to.meta.titel as string | undefined)
})

createApp(App).use(router).mount('#app')
