# Campos sugeridos para GraphRAG / Neo4j

Objetivo: mantener una metadata consistente en Chroma (colección `python_knowledge`) para facilitar GraphRAG y la ingesta en Neo4j.

Convenciones generales
- Claves en snake_case, minúsculas.
- Fechas en ISO 8601 (UTC) — ejemplo: 2024-05-17T12:34:56Z.
- Identificadores: usar el id de Chroma como identificador único (`agent_id`, `document_id`, `chunk_id`) cuando corresponda.
- node_type: valor entre `"Document"`, `"Chunk"`, `"SubAgent"` (Capitalized).
- framework y agent_category en minúsculas (ej. "langchain", "deepagents").
- linked_for_neo4j: booleano (true/false) — marca si el registro está preparado para exportar.

Campos sugeridos (mínimo recomendado)
- id (string): id generado por Chroma (no duplicar).
- node_type (string): "Document" | "Chunk" | "SubAgent".
- framework (string): p.ej. "langchain".
- agent_category (string): p.ej. "deepagents".
- agent_id (string|null): para SubAgent, usa el id de Chroma; para Document/Chunk puede ser null.
- parent_doc_id (string|null): id del Document padre (para Chunk) o id relacionado.
- file_path (string|null): ruta o URL del origen del documento.
- chunk_index (integer|null): índice secuencial del chunk dentro del documento.
- text_hash (string|null): hash SHA256 del texto del chunk.
- created_at (string|null): timestamp ISO 8601 de ingestión.
- category (string|null): etiquetas temáticas, preferiblemente CSV o lista serializada.
- source (string|null): origen (p.ej. "agent_generation", "manual", "github_repo").
- linked_for_neo4j (boolean): true si listo para exportar/crear nodos.

Campos opcionales útiles
- language (string): idioma del contenido, p.ej. "en" / "es".
- confidence (number|null): confianza del vector embedding o extracción.
- tags (list|null): lista de etiquetas estructurada.

Ejemplo de metadata final sugerida
{
  "id": "<chroma-id>",
  "node_type": "SubAgent",
  "framework": "langchain",
  "agent_category": "deepagents",
  "agent_id": "<chroma-id>",
  "parent_doc_id": null,
  "file_path": "/path/to/source.py",
  "chunk_index": null,
  "text_hash": "to_fill",
  "created_at": "2024-05-17T12:34:56Z",
  "category": "deepagents",
  "source": "agent_generation",
  "linked_for_neo4j": true
}

Reglas para futuros chunks / ingestión
1. Al crear un Document, generar su id (Chroma lo hace). Rellenar file_path y created_at.
2. Al chunkear un documento:
   - asignar parent_doc_id = id del Document padre.
   - chunk_index = 0,1,2,... por documento.
   - text_hash = sha256(text) para deduplicación.
   - node_type = "Chunk"; linked_for_neo4j = true/false según política.
3. Para agent-generated content (SubAgents): node_type="SubAgent", framework="langchain", agent_category="deepagents", agent_id = chroma id.
4. Mantener category y source para búsqueda rápida.
5. Si hay relación semántica entre chunks o entre agentes y documentos, guardar parent_doc_id o campos relacionales explícitos (p.ej. created_by_agent_id).

Mapeo recomendado a Neo4j
- Nodos:
  - Document: { document_id: id, file_path, created_at, category, source }
  - Chunk: { chunk_id: id, chunk_index, text_hash, category, source }
  - SubAgent: { agent_id: agent_id, framework, agent_category, category, source }
- Relaciones:
  - (Chunk)-[:CHUNK_OF]->(Document) usando parent_doc_id
  - (SubAgent)-[:GENERATED]->(Document) o (SubAgent)-[:CREATED]->(Chunk) si aplica (usar agent_id -> document_id / chunk_id)

Ejemplo Cypher (snippet)
MERGE (s:SubAgent {agent_id: $agent_id})
SET s.framework = $framework, s.agent_category = $agent_category, s.source = $source

MERGE (d:Document {document_id: $document_id})
SET d.file_path = $file_path, d.created_at = $created_at, d.category = $category

MERGE (c:Chunk {chunk_id: $chunk_id})
SET c.chunk_index = $chunk_index, c.text_hash = $text_hash

MERGE (c)-[:CHUNK_OF]->(d)
MERGE (s)-[:GENERATED]->(d)

Buenas prácticas y checklist antes de exportar
- Validar que parent_doc_id referencie ids existentes.
- Asegurar chunk_index y text_hash para evitar duplicados.
- Establecer linked_for_neo4j = true solo cuando los campos obligatorios estén presentes.
- Mantener un proceso de enriquecimiento automático (script) que corrija/metadatee nuevos chunks.

Notas sobre la actualización realizada
- Se han actualizado 5 registros para añadir:
  node_type: "SubAgent"
  framework: "langchain"
  agent_category: "deepagents"
  agent_id: <id correspondiente>
  parent_doc_id: null
  linked_for_neo4j: true

Ids actualizados:
- 6b3bdf00-8772-4a51-8027-a7f0623ad676
- 54364bbf-e67a-4305-bdd6-f09bf18c433e
- d1152035-4be5-4456-8aee-6e059f881908
- bc8d0d85-5b63-4b4a-89e5-2fbba9bcb4a0
- 078ca74b-b8ec-4011-b94e-122a70fb45ad

Mantén este archivo como referencia y actualiza su sección "Campos sugeridos" si añades nuevas necesidades.
