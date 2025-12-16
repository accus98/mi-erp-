import { defineStore } from 'pinia'
import { rpc } from '../api/rpc'

export const useMenuStore = defineStore('menu', {
    state: () => ({
        menus: [],     // All menus (tree)
        currentApp: null, // Active App (e.g., Sales)
        currentAction: null,
        loading: false,
        error: null // Debug Error
    }),

    getters: {
        // Apps are top-level menus
        apps: (state) => state.menus,
        // Sidebar depends on current App
        currentSidebar: (state) => state.currentApp ? state.currentApp.children : []
    },

    actions: {
        async fetchMenus() {
            this.loading = true
            this.error = null
            console.log("Fetching Menus (Start)...");
            try {
                const result = await rpc.call('ir.ui.menu', 'load_menus', [])
                console.log("Menus Loaded: " + (result ? result.length : 'null'));
                this.menus = result
            } catch (error) {
                console.error("Error loading menus:", error)
                this.error = error.message || error.toString();
            } finally {
                this.loading = false
            }
        },

        selectApp(menu) {
            this.currentApp = menu
            // Optional: Navigate to default action if needed
            // If the app itself has an action, execute it?
            if (menu.action) {
                this.executeAction(menu.action);
            }
        },

        goHome() {
            this.currentApp = null
            this.currentAction = null
        },

        async executeAction(actionId) {
            if (!actionId) return;
            try {
                const actions = await rpc.call('ir.actions.act_window', 'search_read', [
                    [['id', '=', actionId]],
                    ['name', 'res_model', 'view_mode']
                ]);
                if (actions && actions.length > 0) {
                    this.currentAction = actions[0];
                }
            } catch (e) {
                console.error(e);
            }
        }
    }
})
