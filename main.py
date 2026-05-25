#!/usr/bin/env python3
import os
import sys

from agentbankz.agents import OrchestratorFactory
from agentbankz.backends import BackendFactory
from agentbankz.tools.obsidian import create_obsidian_tools
from agentbankz.tools.zapier import create_zapier_tools

# =====================================================================
# 1. CONFIGURACIÓN DE STORAGE Y BACKENDS (HÍBRIDO)
# =====================================================================
backend_factory = BackendFactory()
backend_map = backend_factory.build_all()

# =====================================================================
# 2. INICIALIZACIÓN DE HERRAMIENTAS DINÁMICAS (MCP SOURCES)
# =====================================================================
mcp_tools_map: dict[str, list] = {}

try:
    zapier_tools = create_zapier_tools()
    print(f"[INFO] Zapier MCP conectado — {len(zapier_tools)} herramientas Gmail disponibles.")
    mcp_tools_map["zapier"] = zapier_tools
except Exception as e:
    print(f"[WARN] No se pudo conectar Zapier MCP: {e}")
    print("[WARN] Las herramientas Gmail no estarán disponibles.")

try:
    obsidian_tools = create_obsidian_tools()
    print(f"[INFO] Obsidian MCP conectado — {len(obsidian_tools)} herramientas de vault disponibles.")
    mcp_tools_map["obsidian"] = obsidian_tools
except Exception as e:
    print(f"[WARN] No se pudo conectar Obsidian MCP: {e}")
    print("[WARN] Las herramientas Obsidian no estarán disponibles.")

# =====================================================================
# 3. CONSTRUCCIÓN DEL ORQUESTADOR (TODO DESDE YAML)
# =====================================================================
orchestrator_factory = OrchestratorFactory(mcp_tools_map=mcp_tools_map)
agent = orchestrator_factory.build_all(backend_map)["main"]

# =====================================================================
# 4. RUNTIME
# =====================================================================
if __name__ == "__main__":
    if not os.environ.get("OPENAI_API_KEY"):
        print("[ERROR] Please set the OPENAI_API_KEY environment variable.", file=sys.stderr)
        sys.exit(1)

    print("[INFO] Orchestrator started successfully. Ready to receive payloads and requests.")
