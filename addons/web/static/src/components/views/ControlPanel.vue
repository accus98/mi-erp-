<template>
  <div class="bg-white border-b border-slate-200 px-4 py-3 flex flex-col md:flex-row md:items-center justify-between gap-4">
    
    <div class="flex items-center gap-4">
      <button class="bg-indigo-600 hover:bg-indigo-700 text-white px-4 py-1.5 rounded text-sm font-medium shadow-sm transition-colors uppercase tracking-wide">
        Nuevo
      </button>

      <nav class="hidden md:flex text-sm text-slate-500">
        <ol class="list-none p-0 inline-flex">
          <li class="flex items-center">
            <span class="text-slate-800 font-semibold">{{ title }}</span>
          </li>
        </ol>
      </nav>
    </div>

    <div class="flex items-center gap-3 flex-1 justify-end">
      
      <div class="relative w-full max-w-md group">
        <span class="absolute inset-y-0 left-0 flex items-center pl-3 text-slate-400 group-focus-within:text-indigo-500">
          <svg class="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" /></svg>
        </span>
        <input 
          type="text" 
          placeholder="Buscar..." 
          class="w-full py-1.5 pl-10 pr-4 text-sm border-b border-slate-300 bg-transparent focus:outline-none focus:border-indigo-600 transition-colors placeholder-slate-400"
        />
      </div>

      <div class="flex items-center border-l border-slate-300 pl-3 gap-2 text-slate-600">
        <span class="text-sm font-mono">1-50 / 200</span>
        
        <div class="flex bg-slate-100 rounded p-0.5">
          <button class="p-1 rounded bg-white shadow-sm text-indigo-600"><svg class="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 6h16M4 10h16M4 14h16M4 18h16" /></svg></button> <button class="p-1 rounded hover:bg-white text-slate-400"><svg class="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 6a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2H6a2 2 0 01-2-2V6zM14 6a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2h-2a2 2 0 01-2-2V6zM4 16a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2H6a2 2 0 01-2-2v-2zM14 16a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2h-2a2 2 0 01-2-2v-2z" /></svg></button> </div>
      </div>

    </div>
  </div>
</template>

<script setup>
defineProps(['title'])
</script>
