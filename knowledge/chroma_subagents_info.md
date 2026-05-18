# Información sobre Subagentes en el Framework DeepAgents

## Subagentes Construidos
| Nombre            | Descripción |
|-------------------|-------------|
| `Runnable`        | Para subagentes ya construidos como un `Runnable` de LangChain/LangGraph. |
| `AsyncSubAgent`   | Para agentes que corren de forma remota y asíncrona mediante `graph_id`. |

## Uso en el Sistema
Cuando utilizas `create_deep_agent`, el sistema procesa estas definiciones para:
1.  **Resolver el modelo y permisos**: Si no se definen, se heredan del contexto global.
2.  **Inyectar Middleware base**: Cada `SubAgent` recibe automáticamente herramientas de sistema como `FilesystemMiddleware` y `SummarizationMiddleware`.
3.  **Habilitar la herramienta `task`**: El `SubAgentMiddleware` utiliza estas especificaciones para exponer la capacidad de delegación al modelo.

## Notas
- **`TypedDict` vs `Class`**: En Python, `TypedDict` se usa aquí para que puedas definir subagentes como diccionarios simples sin instanciar clases complejas, facilitando la configuración desde archivos YAML o JSON.
- **Aislamiento**: Los subagentes operan con un estado filtrado para evitar que el historial irrelevante del padre contamine su contexto.