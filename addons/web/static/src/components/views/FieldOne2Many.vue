<template>
  <div class="border rounded-lg overflow-hidden border-slate-200">
    <table class="w-full text-left bg-white text-sm">
      <!-- HEADER -->
      <thead class="bg-slate-50 border-b border-slate-200 text-slate-500 font-medium">
         <tr>
           <th v-for="col in columns" :key="col.name" class="px-4 py-2 uppercasex text-xs tracking-wide">
             {{ col.string }}
           </th>
           <th class="w-10"></th>
         </tr>
      </thead>
      
      <!-- BODY -->
      <tbody class="divide-y divide-slate-100">
         <tr v-for="(row, idx) in rows" :key="row.id || idx" class="hover:bg-slate-50 group">
            
            <td v-for="col in columns" :key="col.name" class="p-0">
               <!-- INLINE INPUT -->
               <input 
                 v-if="col.type === 'char' || col.type === 'float' || col.type === 'integer'"
                 v-model="row[col.name]"
                 @change="onChangeLine(row, idx)"
                 class="w-full px-4 py-2 border-0 bg-transparent focus:ring-inset focus:ring-2 focus:ring-indigo-500 outline-none"
                 :class="{'text-right font-mono': ['float','integer'].includes(col.type)}"
               >
               <span v-else class="px-4 py-2 block text-slate-400 italic">Not supported</span>
            </td>

            <!-- DELETE BUTTON -->
            <td class="text-center px-2">
               <button 
                 @click="removeLine(idx)" 
                 class="text-slate-300 hover:text-red-500 transition-colors"
                 tabindex="-1"
               >
                 &times;
               </button>
            </td>
         </tr>
      </tbody>
      
      <!-- FOOTER ADD -->
      <tfoot>
         <tr>
           <td :colspan="columns.length + 1" class="p-2 bg-slate-50 border-t border-slate-200">
              <button 
                 @click="addLine" 
                 class="text-indigo-600 hover:text-indigo-800 font-medium text-sm flex items-center space-x-1"
               >
                 <span>+ Add an item</span>
               </button>
           </td>
         </tr>
      </tfoot>
    </table>
  </div>
</template>

<script setup>
import { ref, onMounted, watch } from 'vue'
import { rpc } from '../../api/rpc'

const props = defineProps(['record', 'fieldName', 'fieldInfo', 'readonly'])
const emit = defineEmits(['update'])

// Columns configuration (Hardcoded for MVP or fetched?)
// In Odoo, <tree> inside O2M defines columns.
// For MVP, we'll fetch 'sale.order.line' fields or use a default list.
const columns = ref([
    { name: 'name', string: 'Description', type: 'char' },
    { name: 'product_uom_qty', string: 'Quantity', type: 'float' },
    { name: 'price_unit', string: 'Unit Price', type: 'float' },
    { name: 'price_subtotal', string: 'Subtotal', type: 'float' }, // Computed?
])

// Local rows state
const rows = ref([])

// Sync from Record (Initial Load)
// record[fieldName] might be list of IDs or data?
// In 'read', O2M usually returns list of IDs: [1, 2, 3]
// We need to FETCH the lines data if they are IDs.
// If they are tuples (commands), we handle them.

async function init() {
    const val = props.record[props.fieldName]
    
    if (Array.isArray(val) && val.length > 0 && typeof val[0] === 'number') {
        // IDs -> Fetch Data
        // Optimization: FormView should have fetched them? 
        // No, 'read' usually just gives IDs for O2M.
        const lineData = await rpc.call(props.fieldInfo.relation, 'read', [val, []])
        rows.value = lineData
    } else if (Array.isArray(val)) {
        // Already commands or data?
        // Assuming empty or commands.
        // If empty:
        rows.value = []
    }
}

// --- Actions ---

function addLine() {
    const defaultVals = { 
        name: '', 
        product_uom_qty: 1.0, 
        price_unit: 0.0, 
        price_subtotal: 0.0,
        id: 'New-' + Date.now() // Virtual ID
    }
    rows.value.push(defaultVals)
    onChangeLine(defaultVals, rows.value.length - 1) // Trigger Change to add (0,0) cmd
}

function removeLine(index) {
    const row = rows.value[index]
    rows.value.splice(index, 1)
    
    // Generate Command
    let cmd
    if (typeof row.id === 'string' && row.id.startsWith('New')) {
        // Just removed from memory, no command needed if we send full list of commands? 
        // No, we must send commands relative to DB.
        // If it was new, we don't send anything if we haven't saved it.
        // BUT syncing logic is complex.
        // Simplified: Parent expects commands.
        // We emit 'change'.
    } else {
        // Existing ID -> Delete
        cmd = [2, row.id]
        emitCommand(cmd)
    }
}

function onChangeLine(row, index) {
    // 1. Generate Command
    let cmd
    if (typeof row.id === 'string' && row.id.startsWith('New')) {
        // Create (0, 0, vals)
        // We send ALL vals every time? Or just what changed?
        // Create needs all required vals.
        cmd = [0, 0, { ...row, id: undefined }] 
        // Note: Removing 'id' from vals
    } else {
        // Update (1, id, vals)
        cmd = [1, row.id, { ...row }]
    }
    
    // 2. Emit Value Update to Parent (Commands)
    // We ideally maintain a "diff" list.
    // Simplifying: We emit the SINGLE command generated by this action.
    // Parent accumulates?
    // OR Parent expects the full list of commands representing the new state?
    // Standard Odoo form sends: [(1, id, vals), (0, 0, vals)...] on SAVE.
    // On CHANGE, we verify via ONCHANGE.
    
    emitCommand(cmd)
    
    // 3. Trigger Onchange (RPC)
    triggerOnchange()
}

function emitCommand(cmd) {
    // Current Commands in Parent?
    // Parent v-model is props.record[fieldName]
    // We assume parent is smart. We emit event 'update-field'
    // Actually standard Vue: emit('update', commands)
    // But we need to APPEND to existing commands in Parent.
    
    // Let's rely on FormView handling this?
    // No, Custom Field usually updates the value.
    // Value = List of commands.
    
    // Hack for MVP:
    // We keep a 'commands' array locally? 
    // No, that duplicates state.
    
    // Let's emit a SINGLE command and let Parent merge it.
    emit('update', cmd)
}

async function triggerOnchange() {
    // Call backend onchange
    // We need to send: { lines: [[0,0,val], [1,id,val]] } (All current state converted to commands)
    
    // Build efficient commands from 'rows'
    const commands = rows.value.map(r => {
        if (typeof r.id === 'string' && r.id.startsWith('New')) {
            return [0, 0, { ...r, id: undefined }]
        } else {
            return [1, r.id, { ...r }] // Update everything? Inefficient but safe for onchange
        }
    })
    
    // rpc.onchange(vals, field, field_onchange)
    const vals = { ...props.record, [props.fieldName]: commands }
    
    // We need to know which method triggers onchange
    // Hardcoded for MVP or Convention: `onchange_${fieldName}`
    const fieldOnchange = { [props.fieldName]: `onchange_${props.fieldName}` }
    
    const res = await rpc.call(props.record.model || 'sale.order', 'onchange', [vals, props.fieldName, fieldOnchange])
    
    if (res.value) {
        // Apply changes (e.g. Total Amount) to Parent
        // We emit 'apply-changes', res.value
        emit('apply-changes', res.value)
    }
}

onMounted(init)
</script>
