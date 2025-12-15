<template>
  <div class="min-h-screen bg-slate-50 flex flex-col items-center justify-center p-10">
    <div class="max-w-5xl w-full">
      <h1 class="text-3xl font-light text-slate-600 mb-10 text-center">
        Bienvenido a <span class="font-bold text-indigo-600">Nexo ERP</span>
      </h1>
      
      <div v-if="loading" class="text-center text-slate-400 animate-pulse">
        Cargando ecosistema...
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
defineProps(['apps', 'loading'])
defineEmits(['select-app'])
</script>
