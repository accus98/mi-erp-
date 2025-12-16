<template>
  <div class="min-h-screen bg-slate-50 flex flex-col items-center justify-center p-10">
    <div class="max-w-5xl w-full">
      <h1 class="text-3xl font-light text-slate-600 mb-10 text-center">
        Bienvenido a <span class="font-bold text-indigo-600">Nexo ERP</span>
      </h1>
      
      <!-- Debug / Error Section -->
      <div v-if="menuStore.error" class="bg-red-100 text-red-700 p-4 rounded-lg mb-6 text-center shadow-sm">
         <p class="font-bold">Error Cargar Menús</p>
         <p>{{ menuStore.error }}</p>
         <button @click="menuStore.fetchMenus()" class="mt-2 text-sm bg-red-200 hover:bg-red-300 px-3 py-1 rounded">Reintentar</button>
      </div>

      <div v-if="loading" class="text-center text-slate-400 animate-pulse">
        Cargando ecosistema...
      </div>

      <div v-else-if="apps.length === 0" class="text-center text-slate-500">
         <div class="p-6 bg-white rounded-lg shadow-sm border border-slate-200 inline-block">
            <p class="mb-4">No hay aplicaciones disponibles.</p>
            <p class="text-xs text-slate-400 mb-4">
                UID: {{ sessionStore.uid }} | SID: {{ sessionStore.sessionId ? sessionStore.sessionId.substring(0,8)+'...' : 'None' }}
            </p>
            <button @click="menuStore.fetchMenus()" class="bg-indigo-600 text-white px-4 py-2 rounded hover:bg-indigo-700">Recargar Menú</button>
            <button @click="sessionStore.logout()" class="ml-2 bg-red-100 text-red-700 px-4 py-2 rounded hover:bg-red-200">Cerrar Sesión</button>
         </div>
      </div>

      <div v-else class="grid grid-cols-2 md:grid-cols-4 gap-6">
        <button 
          v-for="app in apps" 
          :key="app.id"
          @click="$emit('select-app', app)"
          class="group relative bg-white rounded-2xl shadow-sm hover:shadow-xl hover:-translate-y-1 transition-all duration-300 p-6 flex flex-col items-center border border-slate-100 overflow-hidden"
        >
          <div class="absolute inset-0 bg-gradient-to-br from-indigo-50 to-white opacity-0 group-hover:opacity-100 transition-opacity"></div>
          
          <div class="relative z-10 w-16 h-16 mb-4 rounded-xl bg-gradient-to-tr from-indigo-500 to-purple-500 text-white flex items-center justify-center shadow-lg group-hover:scale-110 transition-transform duration-300">
             <span class="text-2xl font-bold uppercase">{{ app.name.charAt(0) }}</span>
          </div>
          
          <span class="relative z-10 text-slate-600 font-medium group-hover:text-indigo-700">
            {{ app.name }}
          </span>
        </button>
      </div>
    </div>
  </div>
</template>

<script setup>
import { useMenuStore } from '@/stores/menu';
import { useSessionStore } from '@/stores/session';

const menuStore = useMenuStore();
const sessionStore = useSessionStore();

defineProps(['apps', 'loading'])
defineEmits(['select-app'])
</script>
