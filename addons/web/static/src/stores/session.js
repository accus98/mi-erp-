import { defineStore } from 'pinia';
import { ref, computed } from 'vue';

export const useSessionStore = defineStore('session', () => {

    // State - Init from LocalStorage if available
    const uid = ref(localStorage.getItem('session_uid') ? parseInt(localStorage.getItem('session_uid')) : null);
    const sessionId = ref(localStorage.getItem('session_sid'));
    const loginName = ref(localStorage.getItem('session_login'));

    // Getters
    const isLoggedIn = computed(() => !!uid.value);

    // Actions
    async function login(username, password) {
        try {
            const response = await fetch('/web/login', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ params: { login: username, password } })
            });

            const data = await response.json();

            if (data.result && data.result.uid) {
                uid.value = data.result.uid;
                sessionId.value = data.result.session_id;
                loginName.value = username;

                // Persist
                localStorage.setItem('session_uid', uid.value);
                localStorage.setItem('session_sid', sessionId.value);
                localStorage.setItem('session_login', loginName.value);

                return true;
            } else {
                throw new Error("Invalid Credentials");
            }

        } catch (e) {
            console.error("Login Failed", e);
            throw e;
        }
    }

    function logout() {
        // Call backend logout if needed
        fetch('/web/session/destroy', { method: 'POST' });
        uid.value = null;
        sessionId.value = null;
        loginName.value = null;

        // Clear persistence
        localStorage.removeItem('session_uid');
        localStorage.removeItem('session_sid');
        localStorage.removeItem('session_login');

        // Reload to clear state completely
        window.location.reload();
    }

    return {
        uid,
        sessionId,
        loginName,
        isLoggedIn,
        login,
        logout
    }
});
