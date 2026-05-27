
import { serve } from "@hono/node-server";
import { LangGraphHttpAgent } from "@ag-ui/langgraph";
import {
  CopilotRuntime,
  createCopilotEndpoint,
} from "@copilotkit/runtime/v2";

// Configuración del agente que apunta al endpoint de FastAPI (puerto 8002)
const langGraphAgent = new LangGraphHttpAgent({
  url: process.env.LANGGRAPH_DEPLOYMENT_URL || "http://localhost:8002",
});

// Inicialización del runtime con el agente registrado como "default"
const runtime = new CopilotRuntime({
  agents: {
    default: langGraphAgent,
  },
});

// Creación del endpoint de API para CopilotKit
const app = createCopilotEndpoint({
  runtime,
  basePath: "/api/copilotkit",
});

// Inicio del servidor en el puerto 4002
serve({ fetch: app.fetch, port: 4002 }, () => {
  console.log("CopilotKit API server running at http://localhost:4002");
});
