<template>
  <div class="bg-white rounded-2xl shadow-sm border border-slate-200 p-6 space-y-3">
    <h3 class="text-sm font-bold text-slate-800">Upload & Queue Settings</h3>
    <div class="grid sm:grid-cols-2 gap-2">
      <label class="text-xs text-slate-600 space-y-1">
        <span>Pipeline queue max size</span>
        <input v-model.number="local.pipeline_queue_maxsize" type="number" min="1" class="w-full border border-slate-300 rounded-lg px-2 py-1.5 text-sm" />
      </label>
      <label class="text-xs text-slate-600 space-y-1">
        <span>Pipeline workers</span>
        <input v-model.number="local.pipeline_worker_count" type="number" min="1" class="w-full border border-slate-300 rounded-lg px-2 py-1.5 text-sm" />
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
  pipeline_queue_maxsize: 32,
  pipeline_worker_count: 1
})

watch(
  () => props.config,
  (value) => {
    local.pipeline_queue_maxsize = value?.pipeline_queue_maxsize ?? 32
    local.pipeline_worker_count = value?.pipeline_worker_count ?? 1
  },
  { immediate: true, deep: true }
)

defineEmits(['save'])
</script>

