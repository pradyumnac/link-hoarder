import vue from "@vitejs/plugin-vue";
import { defineConfig, loadEnv } from "vite";

export default defineConfig(({ mode }) => {
  const environment = loadEnv(mode, process.cwd(), "VITE_");
  const apiKey = environment.VITE_API_KEY;
  const abSwitchingEnabled =
    mode === "test" || environment.VITE_AB_SWITCHING_ENABLED === "true";

  return {
    define: {
      __AB_SWITCHING_ENABLED__: JSON.stringify(abSwitchingEnabled),
    },
    plugins: [vue()],
    server: {
      host: "127.0.0.1",
      proxy: {
        "/api": {
          changeOrigin: true,
          configure(proxy) {
            if (apiKey) {
              proxy.on("proxyReq", (request) => {
                request.setHeader("X-API-Key", apiKey);
              });
            }
          },
          target: "http://127.0.0.1:8000",
        },
      },
    },
    test: {
      environment: "jsdom",
    },
  };
});
