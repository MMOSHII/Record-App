<template>
  <div class="bg-white rounded-2xl shadow-sm border border-slate-200 p-6 space-y-3">
    <h3 class="text-sm font-bold text-slate-800">Performance Limits</h3>
    <div class="grid sm:grid-cols-2 gap-2">
      <label class="text-xs text-slate-600 space-y-1">
        <span>Pipeline timeout (s)</span>
        <input v-model.number="local.pipeline_task_timeout_seconds" type="number" min="1" class="w-full border border-slate-300 rounded-lg px-2 py-1.5 text-sm" />
      </label>
      <label class="text-xs text-slate-600 space-y-1">
        <span>Rate limit / minute</span>
        <input v-model.number="local.rate_limit_requests_per_minute" type="number" min="1" class="w-full border border-slate-300 rounded-lg px-2 py-1.5 text-sm" />
      </label>
    </div>
    <button type="button" @click="$emit('save', local)" class="px-3 py-2 text-xs font-semibold rounded-lg border border-slate-200 bg-slate-50">Save</button>
  </div>
</template>

<script setup>
import { reactive, watch } from 'vue'

const props = defineProps({
  config: { type: Object, default: () => ({}) }
})

const local = reactive({
  pipeline_task_timeout_seconds: 900,
  rate_limit_requests_per_minute: 120
})

watch(
  () => props.config,
  (value) => {
    local.pipeline_task_timeout_seconds = value?.pipeline_task_timeout_seconds ?? 900
    local.rate_limit_requests_per_minute = value?.rate_limit_requests_per_minute ?? 120
  },
  { immediate: true, deep: true }
)

defineEmits(['save'])
</script>

