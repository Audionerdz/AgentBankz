#!/usr/bin/env python3
import os
import sys

from agentbankz.agents import OrchestratorFactory
from agentbankz.backends import BackendFactory
from agentbankz.tools.zapier import create_zapier_tools

# =====================================================================
# 1. CONFIGURACIÓN DE STORAGE Y BACKENDS (HÍBRIDO)
# =====================================================================
backend_factory = BackendFactory()
backend_map = backend_factory.build_all()

# =====================================================================
# 2. INICIALIZACIÓN DE HERRAMIENTAS DINÁMICAS (ZAPIER MCP)
# =====================================================================
try:
    zapier_tools = create_zapier_tools()
    print(f"[INFO] Zapier MCP conectado — {len(zapier_tools)} herramientas Gmail disponibles.")
except Exception as e:
    print(f"[WARN] No se pudo conectar Zapier MCP: {e}")
    print("[WARN] Las herramientas Gmail no estarán disponibles.")
    zapier_tools = []

# =====================================================================
# 3. CONSTRUCCIÓN DEL ORQUESTADOR (TODO DESDE YAML)
# =====================================================================
orchestrator_factory = OrchestratorFactory(zapier_tools=zapier_tools)
agent = orchestrator_factory.build_all(backend_map)["main"]

# =====================================================================
# 4. RUNTIME
# =====================================================================
if __name__ == "__main__":
    if not os.environ.get("OPENAI_API_KEY"):
        print("[ERROR] Please set the OPENAI_API_KEY environment variable.", file=sys.stderr)
        sys.exit(1)

    print("[INFO] Orchestrator started successfully. Ready to receive payloads and requests.")
