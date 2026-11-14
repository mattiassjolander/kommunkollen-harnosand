import { createApp } from 'vue'
import { createRouter, createWebHistory } from 'vue-router'
import '@fontsource/inter/400.css'
import '@fontsource/inter/600.css'
import './styles/tokens.css'
import App from './App.vue'
import DatakallorView from './views/DatakallorView.vue'
import EkonomiView from './views/EkonomiView.vue'
import FlodenView from './views/FlodenView.vue'
import OversiktView from './views/OversiktView.vue'
import BehandlingView from './views/politik/BehandlingView.vue'
import LedamotView from './views/politik/LedamotView.vue'
import LedamoterView from './views/politik/LedamoterView.vue'
import PolitikView from './views/politik/PolitikView.vue'
import SammantradeView from './views/politik/SammantradeView.vue'

const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/', component: OversiktView, meta: { titel: 'Översikt' } },
    { path: '/ekonomi', component: EkonomiView, meta: { titel: 'Ekonomi' } },
    { path: '/floden', component: FlodenView, meta: { titel: 'Ekonomiska flöden' } },
    { path: '/politik', component: PolitikView, meta: { titel: 'Politik och beslut' } },
    { path: '/politik/sammantraden/:id', component: SammantradeView, meta: { titel: 'Sammanträde' } },
    {
      path: '/politik/sammantraden/:id/paragraf/:paragraf',
      component: BehandlingView,
      meta: { titel: 'Behandling' },
    },
    { path: '/politik/ledamoter', component: LedamoterView, meta: { titel: 'Ledamöter' } },
    { path: '/politik/ledamoter/:id', component: LedamotView, meta: { titel: 'Ledamot' } },
    { path: '/datakallor', component: DatakallorView, meta: { titel: 'Datakällor' } },
  ],
})

createApp(App).use(router).mount('#app')
