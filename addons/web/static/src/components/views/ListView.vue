<template>
  <div class="flex flex-col h-full bg-white">
    
    <ControlPanel :title="model" />

    <div class="flex-1 overflow-auto relative">
      <div v-if="loading" class="flex justify-center items-center h-full text-slate-400">
        Cargando vista...
      </div>

      <table v-else class="w-full text-left border-collapse">
        <thead class="bg-slate-50 sticky top-0 z-10 shadow-sm">
          <tr class="text-xs font-bold text-slate-700 border-b border-slate-300">
            <th class="w-10 px-4 py-3 text-center">
              <input type="checkbox" class="rounded border-slate-300 text-indigo-600 focus:ring-indigo-500 cursor-pointer">
            </th>
            
            <th 
              v-for="col in columns" 
              :key="col.name" 
              class="px-3 py-2 uppercase tracking-wide cursor-pointer hover:text-indigo-600 select-none group"
            >
              {{ col.string }}
              <span class="invisible group-hover:visible ml-1 text-slate-400">↓</span>
            </th>
          </tr>
        </thead>

        <tbody class="divide-y divide-slate-100 text-sm text-slate-700">
          <tr 
            v-for="record in records" 
            :key="record.id" 
            @click="$emit('open-record', record.id)"
            class="hover:bg-slate-50 transition-colors cursor-pointer group"
          >
            <td class="px-4 py-2 text-center" @click.stop>
              <input type="checkbox" class="rounded border-slate-300 text-indigo-600 focus:ring-indigo-500 cursor-pointer opacity-0 group-hover:opacity-100 focus:opacity-100 transition-opacity">
            </td>

            <td v-for="col in columns" :key="col.name" class="px-3 py-1.5">
              
              <!-- Widgets / Field Types -->
              <span 
                v-if="col.name === 'state'" 
                :class="getStatusColor(record[col.name])"
                class="px-2 py-0.5 rounded-full text-xs font-bold uppercase tracking-wide"
              >
                {{ record[col.name] }}
              </span>

              <span v-else-if="col.type === 'float' || col.name.includes('amount') || col.name.includes('price')" class="font-mono font-medium">
                {{ formatCurrency(record[col.name]) }}
              </span>

              <span v-else-if="col.type === 'datetime'">
                 {{ formatDate(record[col.name]) }}
              </span>

              <span v-else>{{ record[col.name] }}</span>

            </td>
          </tr>
        </tbody>
        
        <tfoot v-if="records.length > 0" class="bg-slate-50 border-t border-slate-300 font-bold text-sm">
           <tr>
             <td class="px-4 py-2"></td>
             <td :colspan="columns.length - 1" class="px-3 py-2 text-right pr-10 text-slate-500">
               Total: <span class="text-slate-900 ml-2 text-base">{{ calculateTotal() }}</span>
             </td>
           </tr>
        </tfoot>
      </table>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted, watch } from 'vue'
import { rpc } from '../../api/rpc'
import ControlPanel from './ControlPanel.vue'

const props = defineProps({
  model: { type: String, required: true },
  // fieldsInfo no longer required, we fetch it
})

const loading = ref(true)
const records = ref([])
const columns = ref([])

// --- XML View Engine ---

async function loadViewAndData() {
  loading.value = true
  try {
    // 1. Fetch Architecture (JSON Format from Backend)
    const viewInfo = await rpc.call(props.model, 'get_view_info', [], { view_type: 'tree' })
    console.log("View Info:", viewInfo)

    // 2. Parse Architecture to build Columns
    const arch = viewInfo.arch
    const fieldsMeta = viewInfo.fields
    
    // We expect arch to be { tag: 'tree', children: [...] }
    const cols = []
    
    function traverse(node) {
      if (node.tag === 'field') {
        const fname = node.attrs.name
        const meta = fieldsMeta[fname]
        if (meta) {
           cols.push({
             name: fname,
             string: node.attrs.string || meta.string, // XML overrides Model string
             type: meta.type,
             widget: node.attrs.widget
           })
        }
      }
      if (node.children) {
        node.children.forEach(traverse)
      }
    }
    
    traverse(arch)
    columns.value = cols

    // 3. Fetch Data based on Columns
    const fieldNames = cols.map(c => c.name)
    const data = await rpc.call(props.model, 'search_read', [[], fieldNames])
    
    records.value = data

  } catch (e) {
    console.error("View Engine Error:", e)
  } finally {
    loading.value = false
  }
}

// --- Formatters ---

function getStatusColor(state) {
  if (!state) return 'bg-slate-100 text-slate-600'
  const s = state.toString().toLowerCase()
  if (['draft','borrador'].includes(s)) return 'bg-sky-100 text-sky-700'
  if (['confirmed','confirmado'].includes(s)) return 'bg-orange-100 text-orange-700'
  if (['done','realizado'].includes(s)) return 'bg-emerald-100 text-emerald-700'
  if (['cancel','cancelado'].includes(s)) return 'bg-slate-100 text-slate-500 line-through'
  return 'bg-slate-100 text-slate-700'
}

function formatCurrency(val) {
  if (val == null) return ''
  return new Intl.NumberFormat('es-ES', { style: 'currency', currency: 'EUR' }).format(val)
}

function formatDate(val) {
  if (!val) return ''
  return new Date(val).toLocaleString()
}

function calculateTotal() {
  // Try to find a monetary field in columns
  const moneyCol = columns.value.find(c => ['amount_total', 'total', 'price_total'].includes(c.name))
  if (!moneyCol) return ''
  
  let total = 0
  records.value.forEach(r => {
    total += (r[moneyCol.name] || 0)
  })
  return formatCurrency(total)
}

watch(() => props.model, loadViewAndData, { immediate: true })

</script>
