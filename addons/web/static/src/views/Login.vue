<template>
  <div class="p-10 bg-red-100 text-red-900 border border-red-500">
     <h1>LOGIN COMPONENT MOUNTED</h1>
     <button class="bg-blue-500 text-white p-2" @click="handleLogin">Fake Login</button>
  </div>
</template>

<script setup>
// import { useSessionStore } from '@/stores/session';
// const session = useSessionStore();

function handleLogin() {
    // session.login('admin','admin');
    alert("Login Clicked");
}
</script>
