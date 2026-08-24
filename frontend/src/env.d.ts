/// <reference types="vite/client" />

declare const __AB_SWITCHING_ENABLED__: boolean;

declare module "*.vue" {
  import type { DefineComponent } from "vue";

  const component: DefineComponent;
  export default component;
}
