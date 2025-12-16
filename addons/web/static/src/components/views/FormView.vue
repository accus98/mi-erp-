<template>
  <div class="flex flex-col h-full bg-white animate-fade-in">
    
    <!-- LOADING -->
    <div v-if="loading" class="flex-1 flex items-center justify-center text-slate-400">
       <span class="animate-pulse">Cargando formulario...</span>
    </div>

    <template v-else>
      <!-- HEADER / CONTROL PANEL -->
      <div class="px-6 py-3 border-b border-slate-200 bg-white flex justify-between items-center sticky top-0 z-20 shadow-sm">
        <div class="flex items-center space-x-4">
           <!-- BREADCRUMBS -->
           <ol class="flex items-center space-x-2 text-sm text-slate-600">
             <li class="hover:text-indigo-600 cursor-pointer" @click="$emit('back')">{{ viewInfo.model }}</li>
             <li class="text-slate-400">/</li>
             <li class="font-medium text-slate-800">{{ record.name || record.display_name || 'Nuevo' }}</li>
           </ol>
        </div>

        <div class="flex items-center space-x-3">
             <!-- ACTION BUTTONS (From XML Header) -->
             <template v-for="(btn, idx) in headerButtons" :key="idx">
                <button 
                  @click="triggerAction(btn)"
                  class="px-3 py-1.5 rounded-md text-sm font-medium transition-colors border"
                  :class="btn.attrs.class === 'btn-primary' ? 'bg-indigo-600 text-white border-transparent hover:bg-indigo-700' : 'bg-white text-slate-700 border-slate-300 hover:bg-slate-50'"
                >
                  {{ btn.attrs.string }}
                </button>
             </template>

             <!-- STATUSBAR (Right Aligned or Separate?) -->
             <!-- Odoo puts StatusBar in Header "ribbon" style usually below buttons or right side -->
             <div v-if="statusBarField" class="ml-4 flex rounded-md border border-slate-300 overflow-hidden text-xs font-medium">
                  <div 
                    v-for="stage in getStatusBarStages()" :key="stage"
                    class="px-3 py-1.5 border-r last:border-r-0 border-slate-200 bg-slate-50 text-slate-500"
                    :class="{'!bg-indigo-50 !text-indigo-700': record[statusBarField] === stage}"
                  >
                    {{ stage }}
                  </div>
             </div>

             <!-- SAVE -->
             <button 
               v-if="!readonly"
               @click="save"
               class="px-4 py-1.5 bg-slate-800 text-white rounded-md text-sm hover:bg-slate-900 shadow-sm"
             >
               Guardar
             </button>
        </div>
      </div>

      <!-- MAIN SHEET -->
      <div class="flex-1 overflow-auto bg-slate-100 p-4 md:p-8">
         <div class="max-w-5xl mx-auto bg-white rounded-xl shadow-sm border border-slate-200 min-h-[500px] flex flex-col">
            
            <!-- SHEET CONTENT -->
            <div class="p-8">
                <!-- If Header was inside Form but outside sheet, we handled it top. 
                     Check Sheet Node -->
                <FormRenderer 
                   v-if="sheetNode" 
                   :node="sheetNode"
                   :record="record"
                   :fieldsInfo="viewInfo.fields"
                   :readonly="readonly"
                />
                
                <div v-else class="text-red-500">
                   Error: No &lt;sheet&gt; found in view.
                </div>
            </div>

         </div>
      </div>
    </template>

  </div>
</template>

<script setup>
import { ref, onMounted, computed } from 'vue'
import { rpc } from '../../api/rpc'
import FormRenderer from './FormRenderer.vue'

const props = defineProps(['model', 'recordId'])
const emit = defineEmits(['back'])

const loading = ref(true)
const viewInfo = ref({}) // { arch, fields }
const record = ref({})
const readonly = ref(false)

// Computed for Architecture Parsing
const sheetNode = computed(() => {
   if (!viewInfo.value.arch) return null
   // Look for <sheet> in children
   // Root tag usually 'form'
   const form = viewInfo.value.arch
   const sheet = form.children.find(c => c.tag === 'sheet')
   return sheet || form // Fallback for simple forms
})

const headerButtons = computed(() => {
   if (!viewInfo.value.arch) return []
   // Look for <header>
   const header = viewInfo.value.arch.children.find(c => c.tag === 'header')
   if (!header) return []
   return header.children.filter(c => c.tag === 'button')
})

const statusBarField = computed(() => {
   if (!viewInfo.value.arch) return null
    // Look for <header> then <field widget="statusbar">
   const header = viewInfo.value.arch.children.find(c => c.tag === 'header')
   if (!header) return null
   const field = header.children.find(c => c.tag === 'field' && c.attrs.widget === 'statusbar')
   return field ? field.attrs.name : null
})

// --- Methods ---

function getStatusBarStages() {
    // Ideally fetch Selection options from fieldsInfo
    const fName = statusBarField.value
    if (!fName) return []
    const field = viewInfo.value.fields[fName]
    if (field && field.selection) {
        return field.selection.map(s => s[0])
    }
    return [record.value[fName]] // Fallback to current value
}

async function triggerAction(btnNode) {
    const method = btnNode.attrs.name
    const type = btnNode.attrs.type
    
    if (type === 'object') {
        if (!props.recordId) {
             alert("Save record first.")
             return 
        }
        await rpc.call(props.model, method, [[props.recordId]])
        await loadData() // Refresh
    }
}

async function save() {
    try {
        if (props.recordId) {
            await rpc.call(props.model, 'write', [[props.recordId], record.value])
        } else {
             const newId = await rpc.call(props.model, 'create', [record.value])
             // Redirect to edit mode (emit prop change? or just reload)
             // We can't change prop, so we emit 'open-record'?
             // For now just reload data pretending we are new ID
             // But props.recordId is prop...
             // Simpler: emit 'record-saved', parent handles routing.
        }
        emit('back') // Go back to list for MVP
    } catch (e) {
        console.error(e)
        alert("Error saving: " + e.message)
    }
}

// --- Load ---

async function loadData() {
    loading.value = true
    try {
        // 1. Get View
        viewInfo.value = await rpc.call(props.model, 'get_view_info', [], { view_type: 'form' })
        
        // 2. Get Record (if ID)
        if (props.recordId) {
             // We need columns? We need all fields in view?
             // Optimized: Fetch fields mentioned in view + id/display_name
             // For MVP: Fetch all fields or '*'
             const [data] = await rpc.call(props.model, 'read', [[props.recordId], []])
             record.value = data
        } else {
             // Default Get
             record.value = {}
        }
    } catch(e) {
        console.error(e)
    } finally {
        loading.value = false
    }
}

onMounted(loadData)

</script>
