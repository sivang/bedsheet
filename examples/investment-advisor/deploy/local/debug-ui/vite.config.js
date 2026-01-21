import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
export default defineConfig({
    plugins: [react()],
    server: {
        proxy: {
            '/invoke': {
                target: 'http://localhost:8000',
                changeOrigin: true,
                rewrite: function (path) { return path.replace(/^\/invoke/, '/invoke'); }
            }
        }
    }
});
