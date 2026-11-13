<script setup lang="ts">
const vyer = [{ till: '/ekonomi', namn: 'Ekonomi' }]
</script>

<template>
  <div class="ram">
    <aside class="nav">
      <div class="ordmarke">
        <span class="namn">Kommunkollen</span>
        <span class="ort">Härnösand</span>
      </div>
      <nav aria-label="Huvudvyer">
        <RouterLink v-for="v in vyer" :key="v.till" :to="v.till" class="navlank">{{ v.namn }}</RouterLink>
      </nav>
    </aside>
    <main class="innehall">
      <RouterView />
    </main>
  </div>
</template>

<style scoped>
.ram {
  display: grid;
  grid-template-columns: 220px 1fr;
  min-height: 100vh;
}
.nav {
  border-right: 1px solid var(--line);
  padding: 24px 16px;
  background: var(--surface);
}
.ordmarke {
  display: flex;
  flex-direction: column;
  margin-bottom: 32px;
}
.namn {
  font-weight: 600;
  font-size: 18px;
}
.ort {
  color: var(--ink-secondary);
}
.navlank {
  display: block;
  padding: 8px 12px;
  border-radius: var(--radius);
  color: var(--ink-secondary);
  text-decoration: none;
}
.navlank:hover {
  background: var(--accent-wash);
  color: var(--ink);
}
.navlank.router-link-active {
  background: var(--accent-wash);
  color: var(--accent);
  font-weight: 600;
}
.innehall {
  padding: 32px 48px;
  max-width: 1440px;
}
</style>
