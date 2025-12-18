import { reactive } from 'vue';

// Debug Logs
export const rpcLogs = reactive([]);

function log(msg) {
    rpcLogs.push(`[${new Date().toLocaleTimeString()}] ${msg}`);
    // Keep last 20 logs
    if (rpcLogs.length > 20) rpcLogs.shift();
}

export const rpc = {
    async call(model, method, args = [], kwargs = {}) {
        const payload = {
            jsonrpc: "2.0",
            method: "call",
            params: {
                model,
                method,
                args,
                kwargs
            },
            id: Math.floor(Math.random() * 1000000)
        };

        log(`RPC Call: ${model}.${method}`);

        // CSRF Token Management
        let csrfToken = localStorage.getItem('csrf_token');
        if (!csrfToken) {
            // Lazy Fetch for existing sessions lacking token
            try {
                const tRes = await fetch('/web/session/token', { method: 'GET', credentials: 'include' });
                if (tRes.ok) {
                    const tData = await tRes.json();
                    if (tData.result && tData.result.token) {
                        csrfToken = tData.result.token;
                        localStorage.setItem('csrf_token', csrfToken);
                    }
                }
            } catch (e) {
                console.warn("RPC: Failed to auto-fetch CSRF token", e);
            }
        }

        let response;
        try {
            response = await fetch('/web/dataset/call_kw', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-Nexo-Session-Id': localStorage.getItem('session_sid') || '',
                    'X-CSRF-Token': csrfToken || ''
                },
                credentials: 'include', // Force sending cookies
                body: JSON.stringify(payload)
            });
        } catch (netErr) {
            log(`Network Error: ${netErr.message}`);
            throw netErr;
        }

        log(`Response Status: ${response.status}`);

        if (!response.ok) {
            if (response.status === 403) {
                console.warn("Session Expired (403). Clearing and Reloading.");
                localStorage.removeItem('session_uid');
                localStorage.removeItem('session_sid');
                localStorage.removeItem('session_login');
                // Allow the app to handle logout naturally or via reload
                window.location.reload();
                return;
            }
            let errorBody = "";
            try {
                // Read text ONLY ONCE to avoid "body stream already read"
                errorBody = await response.text();
            } catch (e) {
                // If reading fails completely
                throw new Error(`HTTP Error: ${response.status}`);
            }

            // Try parse as JSON
            try {
                const errData = JSON.parse(errorBody);
                if (errData && errData.error) {
                    const serverMsg = errData.error.message || JSON.stringify(errData.error);
                    const serverType = errData.error.type || "Error";
                    const msg = `${serverType}: ${serverMsg}`;
                    log(`Server Error (${response.status}): ${msg}`);
                    throw new Error(msg);
                }
            } catch (jsonErr) {
                // Ignore JSON parse error, use raw text
            }

            // Fallback to raw text
            if (errorBody) {
                const snippet = errorBody.substring(0, 300);
                console.error("Raw Error Response:", errorBody);
                log(`Server Error (${response.status}): ${snippet}`);
                throw new Error(`Server Error: ${snippet}`);
            }

            log(`HTTP Error: ${response.status}`);
            throw new Error(`HTTP Error: ${response.status}`);
        }

        try {
            const data = await response.json();
            if (data.error) {
                log(`RPC Error: ${data.error.message}`);
                console.error("RPC Error", data.error);
                const errorMsg = (data.error.data && data.error.data.message) ? data.error.data.message : data.error.message;
                const errorObj = new Error(errorMsg);
                errorObj.details = data.error.data;
                throw errorObj;
            }
            log(`Success. Result len: ${data.result ? JSON.stringify(data.result).length : 'null'}`);
            return data.result;
        } catch (jsonErr) {
            if (jsonErr.message && jsonErr.message.includes('RPC Error')) throw jsonErr;
            log(`JSON Parse Error: ${jsonErr.message}`);
            throw jsonErr;
        }
    }
};


