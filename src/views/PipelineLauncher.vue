<template>
  <div class="hidden" />
</template>

<script setup>
import { onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { useAppStore } from '../stores/appStore'

const router = useRouter()
const store = useAppStore()

onMounted(() => {
  store.openPipelineModal()
  router.replace('/')
})
</script>

