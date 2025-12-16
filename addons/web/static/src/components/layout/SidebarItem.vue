<template>
  <div class="space-y-1">
    <div v-if="menu.children && menu.children.length > 0">
      <button 
        @click="toggle"
        class="w-full flex items-center justify-between px-3 py-2 text-sm font-medium text-slate-300 rounded-md hover:bg-slate-800 hover:text-white transition-colors"
      >
        <span>{{ menu.name }}</span>
        <svg :class="{'rotate-90': isOpen}" class="w-4 h-4 transition-transform text-slate-500" fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 5l7 7-7 7" />
        </svg>
      </button>
      
      <div v-if="isOpen" class="pl-4 mt-1 border-l border-slate-700">
        <SidebarItem 
          v-for="child in menu.children" 
          :key="child.id" 
          :menu="child" 
          @action-clicked="$emit('action-clicked', $event)"
        />
      </div>
    </div>

    <button 
      v-else 
      @click="$emit('action-clicked', { actionId: menu.action, label: menu.name })"
      class="w-full text-left px-3 py-2 text-sm text-slate-400 rounded-md hover:bg-indigo-600 hover:text-white transition-all"
    >
      {{ menu.name }}
    </button>
  </div>
</template>

<script setup>
import { ref } from 'vue'

const props = defineProps(['menu'])
const emit = defineEmits(['action-clicked'])
const isOpen = ref(false)

function toggle() {
  isOpen.value = !isOpen.value
}
</script>
