<template>
  <div class="flex flex-col h-full bg-white">
    <div class="px-6 py-4 border-b border-slate-100 flex justify-between items-center bg-slate-50/50">
      <div class="flex items-center space-x-4">
        <button 
          @click="$emit('back')"
          class="text-slate-500 hover:text-indigo-600 transition-colors flex items-center space-x-1 font-medium text-sm"
        >
          <span>← Volver a la lista</span>
        </button>
      </div>
      <div class="space-x-2">
        <button class="px-4 py-2 bg-indigo-600 text-white rounded-lg shadow-sm hover:bg-indigo-700 font-medium text-sm transition-all">
          Guardar
        </button>
      </div>
    </div>

    <div class="p-10 flex-1 overflow-auto flex items-center justify-center">
      <div class="text-center border-2 border-dashed border-slate-200 rounded-2xl p-12 w-full max-w-2xl bg-slate-50/30">
        <p class="text-xl text-slate-400 font-light mb-4">Formulario en Construcción</p>
        <div class="inline-flex gap-4 text-xs font-mono text-slate-500">
           <span class="bg-white px-3 py-1 rounded border border-slate-200">Modelo: {{ model }}</span>
           <span class="bg-white px-3 py-1 rounded border border-slate-200">ID: {{ recordId || 'New' }}</span>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
defineProps(['model', 'recordId'])
defineEmits(['back'])
</script>
