import { createApp } from 'vue'
import { createRouter, createWebHistory } from 'vue-router'
import '@fontsource/inter/400.css'
import '@fontsource/inter/600.css'
import './styles/tokens.css'
import App from './App.vue'
import DatakallorView from './views/DatakallorView.vue'
import EkonomiView from './views/EkonomiView.vue'
import FlodenView from './views/FlodenView.vue'

const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/', redirect: '/ekonomi' },
    { path: '/ekonomi', component: EkonomiView, meta: { titel: 'Ekonomi' } },
    { path: '/floden', component: FlodenView, meta: { titel: 'Ekonomiska flöden' } },
    { path: '/datakallor', component: DatakallorView, meta: { titel: 'Datakällor' } },
  ],
})

createApp(App).use(router).mount('#app')
