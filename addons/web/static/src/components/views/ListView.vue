<template>
  <div class="flex flex-col h-full bg-white">
    
    <ControlPanel :title="model" />

    <div class="flex-1 overflow-auto relative">
      <table class="w-full text-left border-collapse">
        <thead class="bg-slate-50 sticky top-0 z-10 shadow-sm">
          <tr class="text-xs font-bold text-slate-700 border-b border-slate-300">
            <th class="w-10 px-4 py-3 text-center">
              <input type="checkbox" class="rounded border-slate-300 text-indigo-600 focus:ring-indigo-500 cursor-pointer">
            </th>
            
            <th 
              v-for="field in fields" 
              :key="field.name" 
              class="px-3 py-2 uppercase tracking-wide cursor-pointer hover:text-indigo-600 select-none group"
            >
              {{ field.string }}
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

            <td v-for="field in fields" :key="field.name" class="px-3 py-1.5">
              
              <span 
                v-if="field.name === 'state'" 
                :class="getStatusColor(record[field.name])"
                class="px-2 py-0.5 rounded-full text-xs font-bold uppercase tracking-wide"
              >
                {{ record[field.name] }}
              </span>

              <span v-else-if="['total', 'amount', 'price'].includes(field.name)" class="font-mono font-medium">
                {{ formatCurrency(record[field.name]) }}
              </span>

              <span v-else>{{ record[field.name] }}</span>

            </td>
          </tr>
        </tbody>
        
        <tfoot v-if="records.length > 0" class="bg-slate-50 border-t border-slate-300 font-bold text-sm">
           <tr>
             <td class="px-4 py-2"></td>
             <td :colspan="fields.length - 1" class="px-3 py-2 text-right pr-10 text-slate-500">
               Total: <span class="text-slate-900 ml-2 text-base">{{ calculateTotal() }}</span>
             </td>
           </tr>
        </tfoot>
      </table>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { rpc } from '../../api/rpc'
import ControlPanel from './ControlPanel.vue'

const props = defineProps({
  model: { type: String, required: true },
  fieldsInfo: { type: Object, required: true }
})

const records = ref([])
const fields = Object.entries(props.fieldsInfo).map(([name, meta]) => ({
  name, 
  string: meta.string
}))

// --- Lógica de Diseño "Odoo" ---

// 1. Colores de estado (Badges)
function getStatusColor(state) {
  if (!state) return 'bg-slate-100 text-slate-600'
  const s = state.toString().toLowerCase()
  if (s === 'draft' || s === 'borrador') return 'bg-sky-100 text-sky-700' // Azul claro
  if (s === 'confirmed' || s === 'confirmado') return 'bg-orange-100 text-orange-700' // Naranja
  if (s === 'done' || s === 'realizado') return 'bg-emerald-100 text-emerald-700' // Verde Odoo
  if (s === 'cancel') return 'bg-slate-100 text-slate-500 line-through'
  return 'bg-slate-100 text-slate-700'
}

// 2. Formato Moneda
function formatCurrency(val) {
  if (!val) return '0.00 €'
  return new Intl.NumberFormat('es-ES', { style: 'currency', currency: 'EUR' }).format(val)
}

// 3. Totales Falsos (Para demo visual)
function calculateTotal() {
  // Sumamos cualquier campo que parezca dinero
  let total = 0
  records.value.forEach(r => {
    if (r.total) total += r.total
    if (r.amount) total += r.amount
  })
  return formatCurrency(total)
}

// --- Carga de Datos ---
async function loadData() {
  try {
    const fieldNames = fields.map(f => f.name)
    // Pedimos datos. NOTA: Si no tienes datos en DB, esto saldrá vacío.
    const data = await rpc.call(props.model, 'search_read', [[], fieldNames])
    
    // --> TRUCO DE DISEÑO: Si no hay datos, inyectamos FALSOS para que veas el diseño <--
    if (data.length === 0) {
      records.value = [
        { id: 1, name: 'SO001', date: '2023-12-01', partner_id: 'Cliente Demo', state: 'borrador', total: 0.00 },
        { id: 2, name: 'SO002', date: '2023-12-05', partner_id: 'Empresa SL', state: 'confirmado', total: 150.50 },
        { id: 3, name: 'SO003', date: '2023-12-10', partner_id: 'Otro Cliente', state: 'realizado', total: 2500.00 },
      ]
    } else {
      records.value = data
    }
  } catch (e) {
    console.error(e)
  }
}

onMounted(loadData)
</script>
