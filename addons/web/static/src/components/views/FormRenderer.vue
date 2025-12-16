<template>
  
  <!-- GROUPS -->
  <div v-if="node.tag === 'group'" class="grid grid-cols-1 md:grid-cols-2 gap-x-8 gap-y-4 mb-4">
    <template v-for="(child, index) in node.children" :key="index">
      <FormRenderer :node="child" :record="record" :fieldsInfo="fieldsInfo" :readonly="readonly" />
    </template>
  </div>

  <!-- NOTEBOOKS -->
  <div v-else-if="node.tag === 'notebook'" class="mt-6 border rounded-lg overflow-hidden border-slate-200">
    <div class="flex border-b border-slate-200 bg-slate-50">
      <button 
        v-for="(page, index) in node.children.filter(c => c.tag === 'page')" 
        :key="index"
        @click="activeTab = index"
        class="px-4 py-2 text-sm font-medium transition-colors"
        :class="activeTab === index ? 'bg-white text-indigo-600 border-b-2 border-indigo-600 -mb-px' : 'text-slate-600 hover:text-slate-800'"
      >
        {{ page.attrs.string }}
      </button>
    </div>
    <div class="p-4 bg-white">
      <template v-for="(page, index) in node.children.filter(c => c.tag === 'page')" :key="index">
        <div v-show="activeTab === index">
            <template v-for="(child, i) in page.children" :key="i">
                <FormRenderer :node="child" :record="record" :fieldsInfo="fieldsInfo" :readonly="readonly" />
            </template>
        </div>
      </template>
    </div>
  </div>

  <!-- FIELDS -->
  <div v-else-if="node.tag === 'field'" class="flex flex-col mb-2">
    <label class="text-xs font-bold text-slate-500 uppercase mb-1">{{ node.attrs.string || fieldsInfo[node.attrs.name]?.string || node.attrs.name }}</label>
    
    <!-- Widget: Statusbar (Usually in Header, but can be field) -->
    <div v-if="node.attrs.widget === 'statusbar'">
       <!-- Handled in FormView Header usually, but if placed in sheet: -->
       <span class="px-2 py-1 bg-slate-100 rounded text-sm">{{ record[node.attrs.name] }}</span>
    </div>

    <!-- Readonly Mode -->
    <div v-else-if="readonly" class="text-slate-800 text-sm font-medium py-1 min-h-[1.5rem] border-b border-dotted border-slate-300">
      {{ formatValue(record[node.attrs.name], fieldsInfo[node.attrs.name]) }}
    </div>

    <!-- Edit Mode -->
    <div v-else>
       <!-- Selection -->
       <select 
         v-if="fieldsInfo[node.attrs.name]?.type === 'selection'"
         v-model="record[node.attrs.name]"
         class="w-full rounded border-slate-300 focus:border-indigo-500 focus:ring-indigo-500 text-sm shadow-sm"
       >
         <option v-for="opt in (fieldsInfo[node.attrs.name].selection || [])" :key="opt[0]" :value="opt[0]">
            {{ opt[1] }}
         </option>
       </select>
       
       <!-- Many2one -->
       <div v-else-if="fieldsInfo[node.attrs.name]?.type === 'many2one'" class="relative">
          <input 
            type="text" 
            :value="record[node.attrs.name]?.[1] || record[node.attrs.name]" 
            readonly
            class="w-full rounded border-slate-300 bg-slate-50 text-slate-500 text-sm cursor-not-allowed"
            placeholder="Search not implemented yet..."
          >
       </div>

        <!-- Date -->
       <input 
         v-else-if="fieldsInfo[node.attrs.name]?.type === 'datetime' || fieldsInfo[node.attrs.name]?.type === 'date'"
         type="date" 
         v-model="record[node.attrs.name]"
         class="w-full rounded border-slate-300 focus:border-indigo-500 focus:ring-indigo-500 text-sm shadow-sm"
       >
       
       <!-- One2Many -->
       <FieldOne2Many
         v-else-if="isValidField(node.attrs.name) && fieldsInfo[node.attrs.name].type === 'one2many'"
         :record="record"
         :fieldName="node.attrs.name"
         :fieldInfo="fieldsInfo[node.attrs.name]"
         :readonly="readonly"
         @update="handleO2MUpdate($event, node.attrs.name)"
         @apply-changes="handleApplyChanges"
       />
       
       <!-- Default Text/Integer -->
       <input 
         v-else
         type="text" 
         v-model="record[node.attrs.name]"
         class="w-full rounded border-slate-300 focus:border-indigo-500 focus:ring-indigo-500 text-sm shadow-sm"
       >
    </div>
  </div>

  <!-- GENERIC CONTAINER (Divs, etc) -->
  <div v-else>
    <template v-if="node.children">
        <FormRenderer v-for="(child, index) in node.children" :key="index" :node="child" :record="record" :fieldsInfo="fieldsInfo" :readonly="readonly" />
    </template>
  </div>

</template>

<script setup>
import { ref } from 'vue'
import FieldOne2Many from './FieldOne2Many.vue'

const props = defineProps({
  node: Object,
  record: Object,
  fieldsInfo: Object,
  readonly: Boolean
})

const activeTab = ref(0)
const emit = defineEmits(['update-record']) // Not fully wired yet, assuming record is mutated

function isValidField(name) {
    return name && props.fieldsInfo && props.fieldsInfo[name]
}

function formatValue(val, meta) {
  if (val == null) return '-'
  if (meta?.type === 'datetime') return new Date(val).toLocaleString()
  if (meta?.type === 'many2one' && Array.isArray(val)) return val[1]
  return val
}

function handleO2MUpdate(cmd, fieldName) {
    // Merge command into record
    // record[fieldName] should be list of commands
    if (!Array.isArray(props.record[fieldName])) {
        // If it was list of IDs, we convert to list of commands?
        // No, mixed mode is bad.
        // If we edit, we switch to command mode?
        // Or we assume standard Odoo: Always commands on write.
        // For MVP: Initialize with [] if not array.
        props.record[fieldName] = []
    }
    // Check if we need to convert initial IDs to Delete/Replace?
    // No, standard is: (6, 0, ids) + new commands. 
    // Simplified: Just append commands to a list created on init or here.
    
    // Actually, 'cmds' can collect logic. 
    // But Mutating `record` array directly is easiest for MVP interaction.
    props.record[fieldName].push(cmd)
}

function handleApplyChanges(changes) {
    // Merge changes from Onchange (e.g. amount_total)
    Object.assign(props.record, changes)
}
</script>
