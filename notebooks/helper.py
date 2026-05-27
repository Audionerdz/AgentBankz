import os
import subprocess
import sys
import threading
import time
import json
from pathlib import Path


FRONTEND_DIR = Path(__file__).resolve().parent / "frontend"


_PACKAGE_JSON = {
    "name": "ag-ui-frontend",
    "private": True,
    "type": "module",
    "scripts": {
        "dev": "vite --port 3002",
        "build": "tsc && vite build",
        "server": "tsx server.ts",
    },
    "dependencies": {
        "react": "^19.0.0",
        "react-dom": "^19.0.0",
        "@copilotkit/react-core": "^1.56.0",
        "@copilotkit/react-ui": "^1.56.0",
        "@copilotkit/runtime": "^1.56.0",
        "@ag-ui/langgraph": "^0.0.33",
        "@hono/node-server": "^1.13.0",
        "hono": "^4.7.0",
    },
    "devDependencies": {
        "vite": "^6.0.0",
        "@vitejs/plugin-react": "^4.3.0",
        "typescript": "^5.6.0",
        "@types/react": "^19.0.0",
        "@types/react-dom": "^19.0.0",
        "tsx": "^4.19.0",
    },
}

_VITE_CONFIG = """\
import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  server: {
    strictPort: true,
    proxy: {
      "/api/copilotkit": "http://localhost:4002",
    },
  },
});
"""

_TSCONFIG = """\
{
  "compilerOptions": {
    "target": "ES2020",
    "module": "ESNext",
    "moduleResolution": "bundler",
    "jsx": "react-jsx",
    "strict": true,
    "esModuleInterop": true,
    "skipLibCheck": true,
    "forceConsistentCasingInFileNames": true,
    "resolveJsonModule": true,
    "isolatedModules": true,
    "noEmit": true
  },
  "include": ["src", "server.ts"]
}
"""

_INDEX_HTML = """\
<!DOCTYPE html>
<html lang="en">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <title>AG-UI Frontend</title>
  </head>
  <body>
    <div id="root"></div>
    <script type="module" src="/src/main.tsx"></script>
  </body>
</html>
"""

_GLOBALS_CSS = """\
*,
*::before,
*::after {
  box-sizing: border-box;
}
body {
  margin: 0;
  font-family: system-ui, -apple-system, sans-serif;
}
"""


def _ensure_dir(path: Path):
    path.mkdir(parents=True, exist_ok=True)


def _write(path: Path, content: str):
    path.write_text(content, encoding="utf-8")


def install_frontend():
    _ensure_dir(FRONTEND_DIR)
    _ensure_dir(FRONTEND_DIR / "src")
    _ensure_dir(FRONTEND_DIR / "public")

    boilerplate = {
        "package.json": json.dumps(_PACKAGE_JSON, indent=2),
        "vite.config.ts": _VITE_CONFIG,
        "tsconfig.json": _TSCONFIG,
        "index.html": _INDEX_HTML,
        "src/globals.css": _GLOBALS_CSS,
    }

    for name, content in boilerplate.items():
        _write(FRONTEND_DIR / name, content)

    result = subprocess.run(
        ["npm", "install"],
        cwd=FRONTEND_DIR,
        capture_output=True,
        text=True,
        shell=(os.name == "nt"),
    )
    if result.returncode == 0:
        print("✓ Frontend dependencies installed")
    else:
        print(f"npm install failed:\n{result.stderr}")


def start_copilot_runtime(port=4002):
    kwargs = dict(shell=(os.name == "nt"))
    process = subprocess.Popen(
        ["npx", "tsx", "server.ts"],
        cwd=FRONTEND_DIR,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        **kwargs,
    )
    time.sleep(2)
    if process.poll() is not None:
        _, stderr = process.communicate()
        print(f"CopilotKit runtime failed to start:\n{stderr}")
        return process
    print(f"✓ CopilotKit runtime started at http://localhost:{port}")
    return process


def start_frontend(port=3002):
    if (FRONTEND_DIR / "server.ts").exists():
        start_copilot_runtime()

    kwargs = dict(shell=(os.name == "nt"))
    process = subprocess.Popen(
        ["npx", "vite", "--port", str(port)],
        cwd=FRONTEND_DIR,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        **kwargs,
    )
    time.sleep(3)
    if process.poll() is not None:
        _, stderr = process.communicate()
        print(f"Frontend failed to start:\n{stderr}")
        return process
    print(f"✓ Frontend started at http://localhost:{port}")
    return process


def start_server(app, port=8002):
    import uvicorn

    def run():
        uvicorn.run(app, host="0.0.0.0", port=port, log_level="info")

    thread = threading.Thread(target=run, daemon=True)
    thread.start()
    time.sleep(2)
    print(f"✓ API server started at http://localhost:{port}")


def load_api_keys():
    try:
        from dotenv import load_dotenv as _load_dotenv
        _load_dotenv()
        print("✓ API keys loaded from .env")
    except ImportError:
        print("⚠ python-dotenv not installed — run: uv add python-dotenv")


def display_app(port=3002):
    url = f"http://localhost:{port}"
    print(f"✓ App running at {url}")
    return url
