import json
import os
from typing import Optional

from langchain_core.tools import tool
from neo4j import GraphDatabase, Driver

_driver: Optional[Driver] = None


def ensure_driver() -> Driver:
    global _driver
    if _driver is not None:
        return _driver

    uri = os.getenv("NEO4J_URI", "bolt://localhost:7687")
    user = os.getenv("NEO4J_USER", "neo4j")
    password = os.getenv("NEO4J_PASSWORD", "neo4j")

    try:
        _driver = GraphDatabase.driver(uri, auth=(user, password))
        _driver.verify_connectivity()
        return _driver
    except Exception as e:
        raise RuntimeError(f"No se pudo conectar a Neo4j en {uri}: {e}")


def _run_query(query: str, params: Optional[dict] = None) -> list:
    with ensure_driver().session() as session:
        result = session.run(query, params or {})
        return [record.data() for record in result]


@tool
def graph_add_entity(
    name: str,
    entity_type: str,
    description: str,
    properties_json: str = "{}",
) -> str:
    """Crea un nodo entidad en el grafo de conocimiento Neo4j.
    Si ya existe un nodo con el mismo name, actualiza sus propiedades.

    Args:
        name: Nombre único de la entidad
        entity_type: Tipo de entidad (e.g. 'concept', 'framework', 'library')
        description: Descripción de la entidad
        properties_json: Propiedades adicionales en JSON string
    """
    try:
        extra = json.loads(properties_json)
    except json.JSONDecodeError as e:
        return f"Error: properties_json no es JSON válido: {e}"

    props = {"name": name, "type": entity_type, "description": description, **extra}

    query = """
    MERGE (n:Entity {name: $name})
    SET n += $props
    RETURN n.name AS name, n.type AS type, n.description AS description
    """
    result = _run_query(query, {"name": name, "props": props})
    return f"Entidad creada/actualizada: {json.dumps(result, indent=2, ensure_ascii=False)}"


@tool
def graph_add_relationship(
    source_name: str,
    target_name: str,
    rel_type: str,
    properties_json: str = "{}",
) -> str:
    """Crea una relación entre dos entidades en Neo4j.
    Si source_name o target_name no existen, los crea automáticamente con tipo 'unknown'.

    Args:
        source_name: Nombre de la entidad origen
        target_name: Nombre de la entidad destino
        rel_type: Tipo de relación (e.g. 'DEPENDS_ON', 'RELATED_TO', 'IMPLEMENTS')
        properties_json: Propiedades adicionales en JSON string
    """
    try:
        extra = json.loads(properties_json)
    except json.JSONDecodeError as e:
        return f"Error: properties_json no es JSON válido: {e}"

    query = """
    MERGE (a:Entity {name: $source_name})
    ON CREATE SET a.type = 'unknown'
    MERGE (b:Entity {name: $target_name})
    ON CREATE SET b.type = 'unknown'
    MERGE (a)-[r:`REL`]->(b)
    SET r.type = $rel_type
    SET r += $props
    RETURN a.name AS source, type(r) AS rel, r.type AS rel_type, b.name AS target
    """
    result = _run_query(query, {
        "source_name": source_name,
        "target_name": target_name,
        "rel_type": rel_type,
        "props": extra,
    })
    return f"Relación creada: {json.dumps(result, indent=2, ensure_ascii=False)}"


@tool
def graph_query_entity(query: str, limit: int = 10) -> str:
    """Busca entidades en el grafo de conocimiento Neo4J cuyo nombre o
    descripción contengan el texto de 'query'. Retorna las entidades
    encontradas junto con sus relaciones.

    Args:
        query: Texto a buscar en nombres y descripciones de entidades
        limit: Número máximo de entidades a retornar
    """
    entity_query = """
    MATCH (n:Entity)
    WHERE n.name CONTAINS $query OR n.description CONTAINS $query
    OPTIONAL MATCH (n)-[r]-(related:Entity)
    WITH n, r, related
    ORDER BY n.name
    RETURN n.name AS entity, n.type AS type, n.description AS description,
           collect(DISTINCT {
               relation: coalesce(type(r), ''),
               related_entity: coalesce(related.name, ''),
               related_type: coalesce(related.type, '')
           }) AS relationships
    LIMIT $limit
    """
    results = _run_query(entity_query, {"query": query, "limit": limit})

    if not results:
        return f"No se encontraron entidades que coincidan con '{query}'."

    output = []
    for row in results:
        rels = [r for r in row["relationships"] if r["related_entity"]]
        output.append(
            f"[{row['type']}] {row['entity']}: {row['description']}"
        )
        for rel in rels:
            output.append(f"  └── {rel['relation']} → {rel['related_entity']} ({rel['related_type']})")

    return "\n".join(output) if output else f"No hay resultados para '{query}'."


@tool
def graph_get_schema() -> str:
    """Retorna el esquema del grafo de conocimiento: labels de nodos,
    tipos de relaciones, y propiedades más comunes. Útil para entender
    la estructura actual del grafo antes de consultar.
    """
    try:
        labels_query = "CALL db.labels() YIELD label RETURN label ORDER BY label"
        rel_types_query = "CALL db.relationshipTypes() YIELD relationshipType AS rel RETURN rel ORDER BY rel"
        prop_query = """
        MATCH (n:Entity)
        WITH keys(n) AS props
        UNWIND props AS prop
        RETURN prop, count(*) AS freq
        ORDER BY freq DESC
        """

        labels = [r["label"] for r in _run_query(labels_query)]
        rel_types = [r["rel"] for r in _run_query(rel_types_query)]
        properties = _run_query(prop_query)

        lines = ["=== ESQUEMA DEL GRAFO NEO4J ==="]
        lines.append(f"\nLabels de nodos ({len(labels)}):")
        for lbl in labels:
            lines.append(f"  - {lbl}")

        lines.append(f"\nTipos de relación ({len(rel_types)}):")
        for rel in rel_types:
            lines.append(f"  - :{rel}")

        lines.append(f"\nPropiedades de Entity ({len(properties)}):")
        for p in properties:
            lines.append(f"  - {p['prop']} (freq: {p['freq']})")

        return "\n".join(lines)
    except Exception as e:
        return f"Error al obtener esquema: {e}"


@tool
def execute_cypher(query: str, params_json: str = "{}") -> str:
    """Ejecuta una consulta Cypher personalizada directamente contra Neo4j.
    ¡Usar con precaución! Prefiere las herramientas específicas cuando sea posible.

    Args:
        query: Consulta Cypher válida
        params_json: Parámetros de la consulta en JSON string
    """
    try:
        params = json.loads(params_json)
    except json.JSONDecodeError as e:
        return f"Error: params_json no es JSON válido: {e}"

    try:
        result = _run_query(query, params)
        return json.dumps(result, indent=2, ensure_ascii=False)
    except Exception as e:
        return f"Error ejecutando Cypher: {e}"
