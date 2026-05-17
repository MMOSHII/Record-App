<template>
  <Teleport to="body">
    <Transition name="pipeline-modal-fade">
      <div v-if="store.state.pipelineUi.isOpen && !store.state.pipelineUi.isMinimized" class="fixed inset-0 z-[70]">
        <button class="absolute inset-0 bg-slate-900/55" aria-label="Close pipeline modal" @click="close" />
        <div class="absolute inset-x-2 top-2 bottom-2 md:inset-x-8 md:top-6 md:bottom-6 bg-slate-50 rounded-2xl shadow-2xl border border-slate-200 overflow-hidden flex flex-col">
          <div class="px-4 py-3 border-b border-slate-200 bg-white flex items-center justify-between">
            <h2 class="text-sm font-bold text-slate-800">Pipeline</h2>
            <div class="flex items-center gap-2">
              <button class="text-xs font-semibold px-2.5 py-1.5 rounded-lg border border-slate-200 bg-slate-50" @click="store.togglePipelineMinimized()">Minimize</button>
              <button class="text-xs font-semibold px-2.5 py-1.5 rounded-lg border border-slate-200 bg-white" @click="close">Close</button>
            </div>
          </div>
          <div class="flex-1 overflow-y-auto p-3 md:p-6">
            <Pipeline />
          </div>
        </div>
      </div>
    </Transition>

    <button
      v-if="store.state.pipelineUi.isOpen && store.state.pipelineUi.isMinimized"
      class="fixed right-4 bottom-4 z-[70] rounded-2xl bg-white border border-slate-200 shadow-lg px-4 py-3 text-left"
      @click="store.togglePipelineMinimized()"
    >
      <p class="text-xs font-bold text-slate-800">Pipeline</p>
      <p class="text-[11px] text-slate-500">{{ pipeline.status }} · step {{ pipeline.currentStep }}/4</p>
    </button>
  </Teleport>
</template>

<script setup>
import Pipeline from '../views/Pipeline.vue'
import { useAppStore } from '../stores/appStore'

const store = useAppStore()
const pipeline = store.state.pipeline

const close = () => {
  store.closePipelineModal()
}
</script>

