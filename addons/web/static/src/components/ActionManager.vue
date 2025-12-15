<template>
  <div class="h-full flex flex-col relative bg-white rounded-xl shadow-sm border border-slate-200 overflow-hidden">
    
    <div v-if="loading" class="absolute inset-0 bg-white/90 z-50 flex flex-col items-center justify-center backdrop-blur-sm">
      <div class="animate-spin rounded-full h-10 w-10 border-b-2 border-indigo-600"></div>
      <span class="mt-3 text-sm text-indigo-600 font-medium animate-pulse">Cargando datos...</span>
    </div>

    <div v-if="error" class="p-8 text-center flex flex-col items-center justify-center h-full">
      <div class="bg-red-50 text-red-600 p-6 rounded-xl shadow-sm max-w-md">
        <p class="font-bold text-lg mb-2">Algo salió mal</p>
        <p class="text-sm opacity-80">{{ error }}</p>
      </div>
    </div>

    <ListView 
      v-if="!loading && !error && currentViewType === 'tree'"
      :model="actionCtx.res_model"
      :fieldsInfo="viewData.fields"
      @open-record="switchToForm"
    />

    <FormView
      v-if="!loading && !error && currentViewType === 'form'"
      :model="actionCtx.res_model"
      :recordId="selectedRecordId"
      @back="switchToTree"
    />

  </div>
</template>

<script setup>
import { ref, watch } from 'vue'
import { rpc } from '../api/rpc'
import ListView from './views/ListView.vue'
import FormView from './views/FormView.vue'

const props = defineProps(['actionId'])

// Estado interno
const loading = ref(false)
const error = ref(null)
const actionCtx = ref({})   // Datos de la acción (modelo, nombre...)
const viewData = ref({})    // Datos de la vista (campos, arquitectura)
const currentViewType = ref('tree') // 'tree' o 'form'
const selectedRecordId = ref(null)  // ID para el formulario

// Cuando cambia el ID de acción (click en menú), reiniciamos todo
watch(() => props.actionId, (newId) => {
  if (newId) loadAction(newId)
}, { immediate: true })

async function loadAction(id) {
  console.log("🚀 ActionManager: Cargando Acción", id)
  loading.value = true
  error.value = null
  currentViewType.value = 'tree' // Por defecto siempre lista

  try {
    // 1. Buscamos la definición de la Acción en DB
    // Nota: ir.actions.act_window es el modelo que guarda "Qué hacer"
    const [action] = await rpc.call('ir.actions.act_window', 'read', [[parseInt(id)]])
    
    if (!action) throw new Error(`Acción ${id} no encontrada o eliminada`)
    
    actionCtx.value = action
    console.log("✅ Acción cargada:", action.name, "| Modelo:", action.res_model)
    
    // 2. Cargamos la definición de la vista (Campos y XML)
    await loadViewDefinition(action.res_model, 'tree')

  } catch (e) {
    console.error("❌ Error en ActionManager:", e)
    error.value = e.message || "Error cargando la acción"
  } finally {
    loading.value = false
  }
}

async function loadViewDefinition(model, type) {
  // Llamamos al método mágico 'get_view_info' del backend
  const result = await rpc.call(model, 'get_view_info', [], { view_type: type })
  viewData.value = result
}

// Navegación interna (Lista <-> Formulario)
function switchToForm(recordId) {
  selectedRecordId.value = recordId
  currentViewType.value = 'form'
}

function switchToTree() {
  selectedRecordId.value = null
  currentViewType.value = 'tree'
  // Opcional: Recargar datos de la lista aquí
}
</script>
