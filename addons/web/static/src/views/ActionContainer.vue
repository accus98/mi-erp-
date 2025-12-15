<template>
  <div class="h-full flex flex-col">
    <!-- Header -->
    <div class="bg-white border-b border-slate-200 px-6 py-4 flex items-center justify-between" v-if="action">
         <h2 class="text-xl font-bold text-slate-800">{{ action.name }}</h2>
         
         <div class="flex space-x-2">
             <!-- View Switchers (MVP) -->
             <button class="p-1.5 rounded hover:bg-slate-100 text-slate-500">
                 <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 6h16M4 10h16M4 14h16M4 18h16"></path></svg>
             </button>
             <button class="p-1.5 rounded hover:bg-slate-100 text-slate-500">
                 <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 6h16M4 12h16m-7 6h7"></path></svg>
             </button>
         </div>
    </div>

    <!-- Empty State -->
    <div v-if="!action" class="flex-1 flex flex-col items-center justify-center bg-slate-50 text-slate-400">
        <svg class="w-16 h-16 mb-4 opacity-50" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 11H5m14 0a2 2 0 012 2v6a2 2 0 01-2 2H5a2 2 0 01-2-2v-6a2 2 0 012-2m14 0V9a2 2 0 00-2-2M5 11V9a2 2 0 012-2m0 0V5a2 2 0 012-2h6a2 2 0 012 2v2M7 7h10" />
        </svg>
        <p class="text-lg font-medium">Seleccione una aplicación para comenzar</p>
    </div>

    <!-- View Content -->
    <div v-else class="flex-1 overflow-hidden p-6 bg-slate-50">
        <!-- List View -->
        <ListView 
            v-if="currentViewType === 'tree'" 
            :model="action.res_model" 
            :fieldsInfo="defaultFieldsInfo"
        />
        
        <!-- Placeholder for Form -->
        <div v-else-if="currentViewType === 'form'" class="bg-white p-6 shadow rounded">
            Form View (WIP)
        </div>
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue';
import { useMenuStore } from '@/stores/menu';
import ListView from '@/components/views/ListView.vue';

const menuStore = useMenuStore();

const action = computed(() => menuStore.currentAction);

const currentViewType = computed(() => {
    if (!action.value) return null;
    // view_mode is string "tree,form"
    const modes = action.value.view_mode.split(',');
    return modes[0]; // Default to first mode
});

const defaultFieldsInfo = {
    'name': { string: 'Nombre' },
    'create_date': { string: 'Fecha Creación' }
};
</script>
