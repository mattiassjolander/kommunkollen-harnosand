<script setup lang="ts">
import type { Temasymbol } from '../hogtider'

/*
 * Symbolen vid logotypen under en högtid (docs/design.md, Högtidsteman). Högst 24 px, tunna linjer,
 * inga gradienter och ingen rörelse. Stjärnan och vågen är platsvarumärkets egna ikoner och används
 * som de är, med formen som mask så att de får linjefärgen i ljust och mörkt läge.
 * Symbolen är dekor: raden i sidhuvudet bär innebörden.
 */
defineProps<{ symbol: Temasymbol }>()
</script>

<template>
  <span class="symbol" data-testid="hogtidssymbol" :data-symbol="symbol" aria-hidden="true">
    <span v-if="symbol === 'stjarnan'" class="ikon stjarnan" />
    <span v-else-if="symbol === 'vagen'" class="ikon vagen" />
    <svg v-else viewBox="0 0 24 24" width="24" height="24">
      <g v-if="symbol === 'gnistor'" class="linje">
        <path d="M12 3v4M12 17v4M3 12h4M17 12h4M5.6 5.6l2.8 2.8M15.6 15.6l2.8 2.8M5.6 18.4l2.8-2.8M15.6 8.4l2.8-2.8" />
      </g>
      <path
        v-else-if="symbol === 'agg'"
        class="linje rosa"
        d="M12 3c-3.6 0-6.5 5.4-6.5 10A6.5 6.5 0 0 0 12 21a6.5 6.5 0 0 0 6.5-8C18.5 8.4 15.6 3 12 3z"
      />
      <g v-else-if="symbol === 'flagga'">
        <!-- Sverigeflaggan i proportionerna 5:2:9 och 4:2:4. Det enda temat med gul och blå fyllyta. -->
        <rect x="2" y="5.75" width="20" height="12.5" class="flaggbla" />
        <rect x="8.25" y="5.75" width="2.5" height="12.5" class="flaggul" />
        <rect x="2" y="10.75" width="20" height="2.5" class="flaggul" />
      </g>
      <g v-else-if="symbol === 'blomkrans'" class="linje">
        <circle cx="12" cy="12" r="6.5" />
        <circle class="gron" cx="12" cy="5.5" r="2.2" />
        <circle class="gron" cx="17.6" cy="8.75" r="2.2" />
        <circle class="gron" cx="17.6" cy="15.25" r="2.2" />
        <circle class="gron" cx="12" cy="18.5" r="2.2" />
        <circle class="gron" cx="6.4" cy="15.25" r="2.2" />
        <circle class="gron" cx="6.4" cy="8.75" r="2.2" />
      </g>
      <g v-else-if="symbol === 'valsedel'" class="linje">
        <rect class="vit" x="5" y="3" width="14" height="18" rx="1" />
        <path d="M8 8h8M8 11.5h8M8 15h5" />
      </g>
      <g v-else-if="symbol === 'ljus'" class="linje">
        <rect class="vit" x="9.5" y="11" width="5" height="10" rx="0.5" />
        <path d="M12 3.5c1.6 1.8 2.2 3 2.2 4.1a2.2 2.2 0 0 1-4.4 0c0-1.1.6-2.3 2.2-4.1z" />
      </g>
    </svg>
  </span>
</template>

<style scoped>
.symbol {
  display: inline-flex;
  width: 24px;
  height: 24px;
  flex: none;
}
svg {
  width: 24px;
  height: 24px;
  overflow: visible;
}
.linje {
  fill: none;
  stroke: var(--hogtid-linje);
  stroke-width: 1.5;
  stroke-linecap: round;
  stroke-linejoin: round;
}
.rosa {
  fill: var(--hogtid-rosa);
}
.gron {
  fill: var(--hogtid-gron);
}
.vit {
  fill: var(--hogtid-vit);
}
.flaggbla {
  fill: var(--flagga-bla);
}
.flaggul {
  fill: var(--flagga-gul);
}
.ikon {
  width: 24px;
  height: 24px;
  background: var(--hogtid-linje);
  mask-size: contain;
  mask-repeat: no-repeat;
  mask-position: center;
}
.stjarnan {
  mask-image: url('/platsvarumarke/ikon-stjarnan.png');
}
.vagen {
  mask-image: url('/platsvarumarke/ikon-vagen.png');
}
</style>
