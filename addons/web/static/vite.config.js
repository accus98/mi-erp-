import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import path from 'path'

export default defineConfig({
    plugins: [vue()],
    // base: '/web/static/dist/', # Commented out for Dev Mode
    base: '/',
    build: {
        outDir: '../dist',
        emptyOutDir: true
    },
    resolve: {
        alias: {
            '@': path.resolve(__dirname, './src')
        }
    },
    server: {
        proxy: {
            '/web': {
                target: 'http://localhost:8000',
                changeOrigin: true
            }
        }
    }
})
