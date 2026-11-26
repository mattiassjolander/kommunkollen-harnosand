<script setup lang="ts">
// Filter på märkning (#162): en lista med märkningarna, med antal när de är kända.
import { computed } from 'vue'
import { MARKNINGAR, type Markningsid } from '../api'

const props = defineProps<{
  modelValue: string
  /** Antal per märkning. Utan antal visas alla märkningar som går att välja. */
  antal?: Partial<Record<Markningsid, number>>
  /** Ta med märkningarna som bara finns på ärenden. */
  arenden?: boolean
}>()
const emit = defineEmits<{ 'update:modelValue': [string] }>()

const val = computed(() =>
  MARKNINGAR.filter((m) => (props.arenden || !m.arende) && (!props.antal || props.antal[m.id] || props.modelValue === m.id)),
)
</script>

<template>
  <label class="filter">
    Märkning
    <select
      :value="modelValue"
      data-testid="markningsfilter"
      @change="emit('update:modelValue', ($event.target as HTMLSelectElement).value)"
    >
      <option value="">Alla</option>
      <option v-for="m in val" :key="m.id" :value="m.id">
        {{ m.namn }}<template v-if="antal"> ({{ antal[m.id] ?? 0 }})</template>
      </option>
    </select>
  </label>
</template>

<style scoped>
.filter {
  display: inline-flex;
  flex-direction: column;
  gap: 4px;
  font-size: 12px;
  color: var(--ink-secondary);
}
select {
  font: inherit;
  font-size: 13px;
  color: var(--ink);
  background: var(--surface);
  border: 1px solid var(--line-strong);
  border-radius: var(--radius);
  padding: 4px 8px;
}
</style>
