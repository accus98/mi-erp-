/**
 * JSON-RPC Bridge
 */

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

        const response = await fetch('/web/dataset/call_kw', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify(payload)
        });

        if (!response.ok) {
            if (response.status === 403) {
                // Session Expired
                console.warn("Session Expired (403). Clearing and Reloading.");
                localStorage.removeItem('session_uid');
                localStorage.removeItem('session_sid');
                localStorage.removeItem('session_login');
                window.location.reload();
                return;
            }
            throw new Error(`HTTP Error: ${response.status}`);
        }

        const data = await response.json();

        if (data.error) {
            // Odoo-like error handling
            console.error("RPC Error", data.error);
            // Use detailed message if available (Odoo style: error.data.message contains the real exception)
            const errorMsg = (data.error.data && data.error.data.message) ? data.error.data.message : data.error.message;
            const errorObj = new Error(errorMsg);
            errorObj.details = data.error.data;
            throw errorObj;
        }

        return data.result;
    }
};
