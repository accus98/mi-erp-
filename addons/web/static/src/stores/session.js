import { defineStore } from 'pinia';
import { ref, computed } from 'vue';

export const useSessionStore = defineStore('session', () => {

    // State - Init from LocalStorage if available
    const uid = ref(localStorage.getItem('session_uid') ? parseInt(localStorage.getItem('session_uid')) : null);
    const sessionId = ref(localStorage.getItem('session_sid'));
    const loginName = ref(localStorage.getItem('session_login'));
    const csrfToken = ref(localStorage.getItem('csrf_token'));

    // Getters
    const isLoggedIn = computed(() => !!uid.value);

    // Debug Logs
    const logs = ref([]);
    function log(msg) { logs.value.push(msg); }

    // Actions
    async function restoreSession() {
        log("Restore: Starting for UID " + uid.value);
        if (!uid.value) {
            log("Restore: No UID, returning false.");
            return false;
        }

        try {
            log("Restore: Fetching /web/session/check...");
            const response = await fetch('/web/session/check', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-Nexo-Session-Id': localStorage.getItem('session_sid') || ''
                },
                credentials: 'include'
            });
            log("Restore: Fetch returned status " + response.status);

            if (!response.ok) {
                log("Restore: Status not OK. Logging out.");
                console.warn("Session Restore Failed: Server rejected session (Status " + response.status + ")");
                logout();
                return false;
            }

            // Update State (including CSRF)
            const data = await response.json();
            if (data.result && data.result.csrf_token) {
                csrfToken.value = data.result.csrf_token;
                localStorage.setItem('csrf_token', csrfToken.value);
            }

            log("Restore: Success. Returning true.");
            return true;
        } catch (e) {
            log("Restore: Exception " + e.message);
            logout();
            return false;
        }
    }

    async function login(username, password) {
        log("Action: login started for " + username);
        try {
            log("Fetching /web/login (Relative)...");
            const response = await fetch('/web/login', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                credentials: 'include',
                body: JSON.stringify({ params: { login: username, password } })
            });
            log("Fetch Status: " + response.status);

            const data = await response.json();
            log("Data received. Valid UID? " + (data.result && data.result.uid));

            if (data.result && data.result.uid) {
                uid.value = data.result.uid;
                sessionId.value = data.result.session_id;
                loginName.value = username;
                csrfToken.value = data.result.csrf_token;

                log("Assigned UID: " + uid.value);

                // Persist
                localStorage.setItem('session_uid', uid.value);
                localStorage.setItem('session_sid', sessionId.value);
                localStorage.setItem('session_login', loginName.value);
                if (csrfToken.value) {
                    localStorage.setItem('csrf_token', csrfToken.value);
                }
                log("Persisted to LocalStorage.");

                return true;
            } else {
                log("Invalid Credentials (no result.uid)");
                throw new Error("Invalid Credentials");
            }

        } catch (e) {
            log("Login Error: " + e.message);
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
        csrfToken.value = null;
        logs.value = []; // Clear logs

        // Clear persistence
        localStorage.removeItem('session_uid');
        localStorage.removeItem('session_sid');
        localStorage.removeItem('session_login');
        localStorage.removeItem('csrf_token');

        // Reload to clear state completely
        window.location.reload();
    }

    return {
        uid,
        sessionId,
        loginName,
        isLoggedIn,
        logs,
        login,
        logout,
        restoreSession,
        log
    }
});
