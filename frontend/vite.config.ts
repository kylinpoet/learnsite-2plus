import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import Components from 'unplugin-vue-components/vite'
import { ElementPlusResolver } from 'unplugin-vue-components/resolvers'

export default defineConfig({
  plugins: [
    vue(),
    Components({
      dts: false,
      resolvers: [ElementPlusResolver({ importStyle: 'css' })],
    }),
  ],
  build: {
    rollupOptions: {
      output: {
        manualChunks(id) {
          const normalizedId = id.replace(/\\/g, '/')
          if (!normalizedId.includes('/node_modules/')) {
            return
          }
          if (
            normalizedId.includes('/node_modules/vue/') ||
            normalizedId.includes('/node_modules/@vue/') ||
            normalizedId.includes('/node_modules/vue-router/')
          ) {
            return 'vue-core'
          }
          if (
            normalizedId.includes('/node_modules/element-plus/es/components/')
          ) {
            const componentMatch = normalizedId.match(/element-plus\/es\/components\/([^/]+)/)
            if (componentMatch?.[1]) {
              return `el-${componentMatch[1]}`
            }
          }
          if (
            normalizedId.includes('/node_modules/element-plus/') ||
            normalizedId.includes('/node_modules/@element-plus/')
          ) {
            return 'el-core'
          }
          if (normalizedId.includes('/node_modules/async-validator/')) {
            return 'form-utils'
          }
          if (normalizedId.includes('/node_modules/dayjs/')) {
            return 'date-utils'
          }
          if (
            normalizedId.includes('/node_modules/lodash-unified/') ||
            normalizedId.includes('/node_modules/lodash/')
          ) {
            return 'shared-utils'
          }
          if (normalizedId.includes('/node_modules/axios/')) {
            return 'http'
          }
        },
      },
    },
  },
  server: {
    port: 5173,
    proxy: {
      '/api': {
        target: 'http://127.0.0.1:8000',
        changeOrigin: true,
      },
    },
  },
})
