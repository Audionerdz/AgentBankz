# Información sobre DeepAgents y FilesystemBackend

El `root_dir` del proyecto depende de **dónde ejecutes el script**, no de dónde está ubicado el archivo `agent.py`.

## Escenarios

### Si ejecutas desde el root del proyecto
```bash
cd /proyecto
python src/agent.py
```
- `Path.cwd()` = `/proyecto`
- `root_dir="data"` → `/proyecto/data`

### Si ejecutas desde la carpeta src
```bash
cd /proyecto/src
python agent.py
```
- `Path.cwd()` = `/proyecto/src`
- `root_dir="data"` → `/proyecto/src/data`

## Solución recomendada
Para que `root_dir` siempre apunte al root del proyecto independientemente de dónde ejecutes el script, usa `__file__`:
```python
from pathlib import Path
from deepagents.backends import FilesystemBackend

# Obtén el directorio padre de src/agent.py (el root del proyecto)
project_root = Path(__file__).parent.parent.resolve()

# Apunta a la carpeta data en el root
data_dir = project_root / "data"

backend = FilesystemBackend(root_dir=str(data_dir), virtual_mode=True)
```
Esto garantiza que:
- Si `agent.py` está en `/proyecto/src/agent.py`
- `project_root` será `/proyecto`
- `data_dir` será `/proyecto/data`

## Notas
- En el CLI, `root_dir` se establece explícitamente al `effective_cwd` si se proporciona, o a `Path.cwd()` por defecto.
- La función `resolve_physical_path` en el CLI también resuelve rutas relativas contra `Path.cwd()`.

### Citations

**File:** libs/deepagents/deepagents/backends/filesystem.py (L130-130)
```python
        self.cwd = Path(root_dir).resolve() if root_dir else Path.cwd()
```

**File:** libs/cli/deepagents_cli/agent.py (L1168-1189)
```python
    # CONDITIONAL SETUP: Local vs Remote Sandbox
    if sandbox is None:
        # ========== LOCAL MODE ==========
        root_dir = effective_cwd if effective_cwd is not None else Path.cwd()
        # ...
```

**File:** libs/cli/deepagents_cli/file_ops.py (L127-167)
```python
def resolve_physical_path(
    path_str: str | None, assistant_id: str | None
) -> Path | None:
    # ...
```