import { createApp } from 'vue'
import { createRouter, createWebHistory } from 'vue-router'
import '@fontsource/inter/400.css'
import '@fontsource/inter/600.css'
import './styles/tokens.css'
import App from './App.vue'
import DatakallorView from './views/DatakallorView.vue'
import EkonomiView from './views/EkonomiView.vue'
import SkatteunderlagView from './views/SkatteunderlagView.vue'
import UndersokningarView from './views/UndersokningarView.vue'
import BudgetOchUtfallView from './views/BudgetOchUtfallView.vue'
import FlodenView from './views/FlodenView.vue'
import KommandeView from './views/KommandeView.vue'
import OversiktView from './views/OversiktView.vue'
import ArendeView from './views/politik/ArendeView.vue'
import AvvikelserView from './views/politik/AvvikelserView.vue'
import BudgetforslagView from './views/politik/BudgetforslagView.vue'
import TidigareBudgetView from './views/politik/TidigareBudgetView.vue'
import BudgetutkastView from './views/politik/BudgetutkastView.vue'
import BehandlingView from './views/politik/BehandlingView.vue'
import KopplingarView from './views/politik/KopplingarView.vue'
import SammantradesplanerView from './views/politik/SammantradesplanerView.vue'
import KalenderView from './views/KalenderView.vue'
import LedamotView from './views/politik/LedamotView.vue'
import LedamoterView from './views/politik/LedamoterView.vue'
import PolitikView from './views/politik/PolitikView.vue'
import ProtokollavvikelserView from './views/politik/ProtokollavvikelserView.vue'
import RattelserView from './views/politik/RattelserView.vue'
import PartitillhorighetView from './views/politik/PartitillhorighetView.vue'
import StatistikView from './views/politik/StatistikView.vue'
import SammantradeView from './views/politik/SammantradeView.vue'
import SammansattningView from './views/politik/SammansattningView.vue'

const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/', component: OversiktView, meta: { titel: 'Översikt' } },
    { path: '/ekonomi', component: EkonomiView, meta: { titel: 'Ekonomi' } },
    { path: '/ekonomi/skatteunderlag', component: SkatteunderlagView, meta: { titel: 'Skatteunderlagsprognos' } },
    { path: '/ekonomi/budget-och-utfall', component: BudgetOchUtfallView, meta: { titel: 'Budget och utfall' } },
    { path: '/floden', component: FlodenView, meta: { titel: 'Ekonomiska flöden' } },
    { path: '/undersokningar', component: UndersokningarView, meta: { titel: 'Undersökningar' } },
    { path: '/politik', component: PolitikView, meta: { titel: 'Politik och beslut' } },
    { path: '/politik/sammantraden/:id', component: SammantradeView, meta: { titel: 'Sammanträde' } },
    {
      path: '/politik/sammantraden/:id/paragraf/:paragraf',
      component: BehandlingView,
      meta: { titel: 'Behandling' },
    },
    { path: '/politik/arenden/:id', component: ArendeView, meta: { titel: 'Ärende' } },
    { path: '/politik/kopplingar', component: KopplingarView, meta: { titel: 'Kopplingar' } },
    { path: '/politik/sammantradesplaner', component: SammantradesplanerView, meta: { titel: 'Sammanträdesplaner' } },
    { path: '/politik/rattelser', component: RattelserView, meta: { titel: 'Rättelser' } },
    { path: '/politik/partitillhorighet', component: PartitillhorighetView, meta: { titel: 'Partitillhörighet' } },
    { path: '/politik/statistik', component: StatistikView, meta: { titel: 'Statistik' } },
    { path: '/politik/avvikelser', component: AvvikelserView, meta: { titel: 'Avvikelser i protokollen' } },
    {
      path: '/politik/protokollavvikelser',
      component: ProtokollavvikelserView,
      meta: { titel: 'Protokollavvikelser att anmäla' },
    },
    { path: '/politik/budget', component: BudgetforslagView, meta: { titel: 'Budgetförslag' } },
    {
      path: '/politik/budget/tidigare/:slag(forslag|planforutsattningar)/:id(\\d+)',
      component: TidigareBudgetView,
      meta: { titel: 'Förra versionen' },
    },
    { path: '/politik/budgetutkast', component: BudgetutkastView, meta: { titel: 'Budgetutkast' } },
    { path: '/politik/ledamoter', component: LedamoterView, meta: { titel: 'Ledamöter' } },
    { path: '/politik/ledamoter/:id', component: LedamotView, meta: { titel: 'Ledamot' } },
    { path: '/politik/sammansattning', component: SammansattningView, meta: { titel: 'Sammansättning' } },
    { path: '/kalender', component: KalenderView, meta: { titel: 'Kalender' } },
    { path: '/kommande', component: KommandeView, meta: { titel: 'Kommande' } },
    { path: '/datakallor', component: DatakallorView, meta: { titel: 'Datakällor' } },
  ],
})

createApp(App).use(router).mount('#app')
