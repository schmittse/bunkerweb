import { resolve } from "path";
import { defineConfig } from "vite";
import vue from "@vitejs/plugin-vue";
import VueI18nPlugin from "@intlify/unplugin-vue-i18n/vite";

// https://vitejs.dev/config/
export default defineConfig({
  plugins: [
    vue(),
    VueI18nPlugin({
      include: resolve(__dirname, "./dashboard/lang/**"),
      jitCompilation: true,
    }),
  ],
  server: {
    host: true,
    port: 3000,
  },
  resolve: {
    // https://vitejs.dev/config/#resolve-extensions
    // Reduce the amount of extensions that Vite will try to resolv
    extensions: [".js", ".json", ".vue", ".css"],
    alias: {
      "@": resolve(__dirname, "./dashboard"),
      "@store": resolve(__dirname, "./dashboard/store"),
      "@utils": resolve(__dirname, "./dashboard/utils"),
      "@layouts": resolve(__dirname, "./dashboard/layouts"),
      "@pages": resolve(__dirname, "./dashboard/pages"),
      "@components": resolve(__dirname, "./dashboard/components"),
      "@assets": resolve(__dirname, "./dashboard/assets"),
      "@lang": resolve(__dirname, "./dashboard/lang"),
      "@public": resolve(__dirname, "./public"),
    },
  },
  build: {
    minify: "esbuild",
    chunkSizeWarningLimit: 1024,
    outDir: "./opt-dashboard",
    emptyOutDir: "./opt-dashboard",
    rollupOptions: {
      input: {
        home: resolve(__dirname, "./dashboard/pages/home/index.html"),
        instances: resolve(__dirname, "./dashboard/pages/instances/index.html"),
        global_config: resolve(
          __dirname,
          "./dashboard/pages/global-config/index.html"
        ),
        jobs: resolve(__dirname, "./dashboard/pages/jobs/index.html"),
      },
    },
  },
});