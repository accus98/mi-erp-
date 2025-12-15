<template>
  <div class="h-full">
    <Login v-if="!session.isLoggedIn" />
    <Layout v-else />
  </div>
</template>

<script setup>
import { useSessionStore } from '@/stores/session';
import Login from '@/views/Login.vue';
import Layout from '@/components/Layout.vue';

const session = useSessionStore();
</script>
