import { createApp } from "vue";
import App from "./App.vue";
import { ApiClient, browserToken } from "./api/client";
import { createCalcStore } from "./pages/calcStore";
import { createDliStore } from "./pages/dliStore";
import { createHistoryStore } from "./pages/historyStore";
import { createOverviewStore } from "./pages/overviewStore";
import { createReferenceStore } from "./pages/referenceStore";
import { createSettingsStore } from "./pages/settingsStore";
import { createSupportStore } from "./pages/supportStore";
import { createTakeoverStore } from "./pages/takeoverStore";
import { createMaintenanceStore } from "./pages/maintenanceStore";
import { viewFrom } from "./lib/view";
import "./styles/tokens.css";
import "./styles/base.css";

const api = new ApiClient(browserToken());
createApp(App, {
  store: createHistoryStore(api),
  dli: createDliStore(api),
  calc: createCalcStore(api),
  settings: createSettingsStore(api),
  overview: createOverviewStore(api),
  takeover: createTakeoverStore(api),
  maintenance: createMaintenanceStore(api),
  support: createSupportStore(api),
  reference: createReferenceStore(api),
  initialView: viewFrom(window.location.search),
}).mount("#app");
