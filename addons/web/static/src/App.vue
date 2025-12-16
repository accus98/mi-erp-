<template>
  <div class="h-full">
    <!-- Login View (Inlined) -->
    <div v-if="!session.isLoggedIn" class="flex min-h-screen flex-col justify-center px-6 py-12 lg:px-8 bg-gray-50">
        <div class="sm:mx-auto sm:w-full sm:max-w-sm">
            <h2 class="mt-10 text-center text-2xl font-bold leading-9 tracking-tight text-gray-900">
                Sign in to Nexo ERP
            </h2>
        </div>

        <div class="mt-10 sm:mx-auto sm:w-full sm:max-w-sm">
                <form class="space-y-6" @submit.prevent="handleLogin">
                    <div>
                        <label for="email" class="block text-sm font-medium leading-6 text-gray-900">Login</label>
                        <div class="mt-2">
                            <input v-model="username" id="email" name="email" type="text" autocomplete="email" required class="block w-full rounded-md border-0 py-1.5 text-gray-900 shadow-sm ring-1 ring-inset ring-gray-300 placeholder:text-gray-400 focus:ring-2 focus:ring-inset focus:ring-indigo-600 sm:text-sm sm:leading-6 pl-3" />
                        </div>
                    </div>

                    <div>
                        <div class="flex items-center justify-between">
                            <label for="password" class="block text-sm font-medium leading-6 text-gray-900">Password</label>
                        </div>
                        <div class="mt-2 relative">
                            <input v-model="password" id="password" name="password" :type="showPassword ? 'text' : 'password'" autocomplete="current-password" required class="block w-full rounded-md border-0 py-1.5 text-gray-900 shadow-sm ring-1 ring-inset ring-gray-300 placeholder:text-gray-400 focus:ring-2 focus:ring-inset focus:ring-indigo-600 sm:text-sm sm:leading-6 pl-3 pr-10" />
                            <button type="button" @click="showPassword = !showPassword" class="absolute inset-y-0 right-0 pr-3 flex items-center text-gray-400 hover:text-gray-600">
                                <span v-if="showPassword">Hide</span>
                                <span v-else>Show</span>
                            </button>
                        </div>
                    </div>

                    <div>
                        <p v-if="error" class="text-red-600 text-sm text-center mb-2">{{ error }}</p>

                        <button type="submit" :disabled="loading" class="flex w-full justify-center rounded-md bg-indigo-600 px-3 py-1.5 text-sm font-semibold leading-6 text-white shadow-sm hover:bg-indigo-500 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-indigo-600 disabled:opacity-50 transition-all">
                            <span v-if="loading">Signing in...</span>
                            <span v-else>Sign in</span>
                        </button>
                    </div>
                </form>
            </div>
    </div>

    <!-- Layout View -->
    <Layout v-else-if="!appLoading" />
    
    <!-- Loading Splash -->
    <div v-if="appLoading" class="fixed inset-0 bg-white flex flex-col items-center justify-center z-50">
        <h2 class="text-2xl font-light text-slate-800 mb-2">Nexo ERP</h2>
        <div class="text-gray-500 text-sm font-mono">{{ loadingStatus }}</div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue';
import { useSessionStore } from '@/stores/session';
import Layout from '@/components/Layout.vue';

const session = useSessionStore();
const username = ref('');
const password = ref('');
const showPassword = ref(false);
const loading = ref(false);
const error = ref(null);
const appLoading = ref(true); // Initial App Load

const loadingStatus = ref("Initializing...");

onMounted(async () => {
    loadingStatus.value = "Checking session...";
    
    // Verify session on startup
    if (session.isLoggedIn) {
        try {
            const isValid = await session.restoreSession();
            if (isValid) {
                 loadingStatus.value = "Session Restored. Loading App...";
            } else {
                 loadingStatus.value = "Session Expired. Redirecting to Login...";
            }
        } catch (e) {
            loadingStatus.value = "Session Error: " + e.message;
        }
    } else {
        loadingStatus.value = "Welcome. Please Sign In.";
    }
    
    // Smooth transition
    setTimeout(() => {
        appLoading.value = false;
    }, 500);
});

async function handleLogin() {
    loading.value = true;
    error.value = null;
    try {
        if (await session.login(username.value, password.value)) {
             console.log("Login OK");
        }
    } catch (e) {
        error.value = "Login Failed: " + (e.message || e);
    } finally {
        loading.value = false;
    }
}
</script>
