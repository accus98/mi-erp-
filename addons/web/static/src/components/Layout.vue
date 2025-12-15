<script setup>
import { onMounted, ref } from 'vue'
import { useMenuStore } from '@/stores/menu'
import { useSessionStore } from '@/stores/session'
import SidebarItem from './layout/SidebarItem.vue' 
import AppSwitcher from './layout/AppSwitcher.vue'
import ActionManager from './ActionManager.vue'
import { Squares2X2Icon } from '@heroicons/vue/24/outline'

const menuStore = useMenuStore()
const sessionStore = useSessionStore()
const currentActionId = ref(null)

onMounted(() => {
  menuStore.fetchMenus()
})

function handleMenuClick(actionId) {
  if (actionId) {
      currentActionId.value = actionId;
      // We don't strictly need menuStore.executeAction if ActionManager does it,
      // but if we want breadcrumbs in store later, might be useful. 
      // For now, local state is sufficient for ActionManager.
  }
}

function selectApp(app) {
    menuStore.selectApp(app);
    currentActionId.value = null; // Reset when switching apps
}

function logout() {
    sessionStore.logout();
}
</script>

<template>
  <AppSwitcher 
    v-if="!menuStore.currentApp" 
    :apps="menuStore.apps" 
    :loading="menuStore.loading"
    @select-app="selectApp"
  />

  <div v-else class="flex h-screen bg-slate-100 overflow-hidden">
    
    <aside class="w-64 bg-slate-900 text-slate-300 flex flex-col shadow-2xl transition-all z-20">
      <div class="h-16 flex items-center px-4 bg-slate-950 border-b border-slate-800">
        <button 
          @click="menuStore.goHome"
          class="p-2 mr-2 rounded-lg hover:bg-slate-800 text-slate-400 hover:text-white transition-colors"
          title="Menú Principal"
        >
          <Squares2X2Icon class="w-6 h-6" />
        </button>
        <span class="font-bold text-white tracking-wide truncate">{{ menuStore.currentApp.name }}</span>
      </div>

      <nav class="flex-1 overflow-y-auto p-4 space-y-2 scrollbar-hide">
        <SidebarItem 
          v-for="menu in menuStore.currentSidebar" 
          :key="menu.id" 
          :menu="menu"
          @action-clicked="handleMenuClick"
        />
        
        <div v-if="menuStore.currentSidebar.length === 0" class="text-sm text-slate-500 text-center mt-10">
          No hay submenús
        </div>
      </nav>
      
       <!-- Quick Logout (Optional) -->
       <div class="p-4 border-t border-slate-800 text-xs text-center text-slate-500 cursor-pointer hover:text-white" @click="logout">
           Cerrar Sesión
       </div>
    </aside>

    <div class="flex-1 flex flex-col min-w-0">
      
      <header class="h-16 bg-white shadow-sm border-b border-slate-200 flex items-center justify-between px-6 z-10">
        <div class="flex items-center text-sm text-slate-500">
          <span class="cursor-pointer hover:text-indigo-600" @click="menuStore.goHome">Home</span>
          <span class="mx-2">/</span>
          <span class="font-medium text-slate-800">{{ menuStore.currentApp.name }}</span>
        </div>

        <div class="flex items-center space-x-4">
           <div class="w-8 h-8 rounded-full bg-indigo-100 text-indigo-600 flex items-center justify-center font-bold text-xs border border-indigo-200 cursor-pointer" @click="logout" title="Logout">
             AD
           </div>
        </div>
      </header>

      <main class="flex-1 overflow-auto p-6 relative bg-slate-100/50">
      
      <ActionManager 
        v-if="currentActionId" 
        :action-id="currentActionId" 
      />
      
      <div v-else class="h-full flex flex-col items-center justify-center text-slate-300 select-none">
         <Squares2X2Icon class="w-24 h-24 mb-6 opacity-10" />
         <span class="text-lg font-medium opacity-40">Seleccione un módulo del menú lateral</span>
      </div>

    </main>
    </div>
  </div>
</template>
