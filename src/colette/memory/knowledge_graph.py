"""Graphiti/Neo4j knowledge graph integration (FR-MEM-002/008).

The knowledge graph is optional.  When disabled via
``knowledge_graph_enabled=False``, the :class:`NullKnowledgeGraphStore`
returns empty results for all operations.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import structlog

from colette.memory.config import MemorySettings
from colette.memory.exceptions import (
    KnowledgeGraphUnavailableError,
    MemoryBackendError,
)
from colette.memory.models import KGEntity, KGRelationship

logger = structlog.get_logger(__name__)


def _dict_to_tuples(d: dict[str, str]) -> tuple[tuple[str, str], ...]:
    return tuple(sorted(d.items()))


class NullKnowledgeGraphStore:
    """No-op implementation used when the knowledge graph is disabled.

    All reads return empty results; all writes are silently ignored.
    """

    async def add_entity(self, entity: KGEntity) -> str:
        logger.debug("kg_noop_add_entity", entity_id=entity.id)
        return entity.id

    async def add_relationship(self, rel: KGRelationship) -> str:
        logger.debug("kg_noop_add_relationship", rel_id=rel.id)
        return rel.id

    async def get_entity(self, entity_id: str) -> KGEntity | None:
        return None

    async def get_neighbors(
        self,
        entity_id: str,
        *,
        hops: int = 1,
    ) -> list[KGEntity]:
        return []

    async def query_temporal(
        self,
        project_id: str,
        *,
        since: datetime | None = None,
        until: datetime | None = None,
    ) -> list[KGEntity]:
        return []

    async def delete_entity(self, entity_id: str) -> None:
        pass


class GraphitiKnowledgeGraphStore:
    """Graphiti/Neo4j-backed implementation of :class:`KnowledgeGraphStore`.

    Uses lazy imports for ``graphiti_core`` and ``neo4j`` since they are
    optional dependencies.
    """

    def __init__(self, settings: MemorySettings) -> None:
        self._settings = settings
        self._driver: Any = None

        if not settings.knowledge_graph_enabled:
            raise KnowledgeGraphUnavailableError("Knowledge graph is disabled in configuration")

    def _ensure_driver(self) -> Any:
        if self._driver is None:
            try:
                from neo4j import GraphDatabase

                self._driver = GraphDatabase.driver(
                    "bolt://localhost:7687",
                    auth=("neo4j", "colette-dev"),
                )
            except Exception as exc:
                raise MemoryBackendError("neo4j", str(exc)) from exc
        return self._driver

    async def add_entity(self, entity: KGEntity) -> str:
        driver = self._ensure_driver()
        props = entity.properties_dict
        try:
            with driver.session() as session:
                session.run(
                    "MERGE (n:Entity {id: $id, project_id: $project_id}) "
                    "SET n.entity_type = $entity_type, n.name = $name, "
                    "n.properties = $properties, "
                    "n.created_at = $created_at, n.valid_at = $valid_at",
                    id=entity.id,
                    project_id=entity.project_id,
                    entity_type=entity.entity_type,
                    name=entity.name,
                    properties=str(props),
                    created_at=entity.created_at.isoformat(),
                    valid_at=entity.valid_at.isoformat(),
                )
        except Exception as exc:
            raise MemoryBackendError("neo4j", str(exc)) from exc

        logger.info("kg_entity_added", entity_id=entity.id, name=entity.name)
        return entity.id

    async def add_relationship(self, rel: KGRelationship) -> str:
        driver = self._ensure_driver()
        try:
            with driver.session() as session:
                session.run(
                    "MATCH (a:Entity {id: $source_id, project_id: $project_id}) "
                    "MATCH (b:Entity {id: $target_id, project_id: $project_id}) "
                    "MERGE (a)-[r:RELATES {id: $id}]->(b) "
                    "SET r.relationship_type = $rel_type, "
                    "r.created_at = $created_at, r.valid_at = $valid_at",
                    id=rel.id,
                    project_id=rel.project_id,
                    source_id=rel.source_id,
                    target_id=rel.target_id,
                    rel_type=rel.relationship_type,
                    created_at=rel.created_at.isoformat(),
                    valid_at=rel.valid_at.isoformat(),
                )
        except Exception as exc:
            raise MemoryBackendError("neo4j", str(exc)) from exc

        logger.info("kg_relationship_added", rel_id=rel.id)
        return rel.id

    async def get_entity(self, entity_id: str) -> KGEntity | None:
        driver = self._ensure_driver()
        try:
            with driver.session() as session:
                result = session.run(
                    "MATCH (n:Entity {id: $id}) WHERE n.expired_at IS NULL RETURN n",
                    id=entity_id,
                )
                record = result.single()
                if record is None:
                    return None
                node = record["n"]
                return KGEntity(
                    id=node["id"],
                    project_id=node.get("project_id", ""),
                    entity_type=node.get("entity_type", ""),
                    name=node.get("name", ""),
                    created_at=datetime.fromisoformat(node["created_at"]),
                    valid_at=datetime.fromisoformat(node["valid_at"]),
                )
        except Exception as exc:
            raise MemoryBackendError("neo4j", str(exc)) from exc

    async def get_neighbors(
        self,
        entity_id: str,
        *,
        hops: int = 1,
    ) -> list[KGEntity]:
        driver = self._ensure_driver()
        try:
            with driver.session() as session:
                result = session.run(
                    f"MATCH (a:Entity {{id: $id}})-[*1..{hops}]-(b:Entity) "
                    "WHERE b.expired_at IS NULL "
                    "RETURN DISTINCT b",
                    id=entity_id,
                )
                entities: list[KGEntity] = []
                for record in result:
                    node = record["b"]
                    entities.append(
                        KGEntity(
                            id=node["id"],
                            project_id=node.get("project_id", ""),
                            entity_type=node.get("entity_type", ""),
                            name=node.get("name", ""),
                            created_at=datetime.fromisoformat(node["created_at"]),
                            valid_at=datetime.fromisoformat(node["valid_at"]),
                        )
                    )
                return entities
        except Exception as exc:
            raise MemoryBackendError("neo4j", str(exc)) from exc

    async def query_temporal(
        self,
        project_id: str,
        *,
        since: datetime | None = None,
        until: datetime | None = None,
    ) -> list[KGEntity]:
        """Query entities by temporal range (FR-MEM-008)."""
        driver = self._ensure_driver()
        since_iso = (since or datetime.min.replace(tzinfo=UTC)).isoformat()
        until_iso = (until or datetime.now(UTC)).isoformat()

        try:
            with driver.session() as session:
                result = session.run(
                    "MATCH (n:Entity {project_id: $project_id}) "
                    "WHERE n.valid_at >= $since AND n.valid_at <= $until "
                    "AND n.expired_at IS NULL "
                    "RETURN n ORDER BY n.valid_at DESC",
                    project_id=project_id,
                    since=since_iso,
                    until=until_iso,
                )
                entities: list[KGEntity] = []
                for record in result:
                    node = record["n"]
                    entities.append(
                        KGEntity(
                            id=node["id"],
                            project_id=node.get("project_id", ""),
                            entity_type=node.get("entity_type", ""),
                            name=node.get("name", ""),
                            created_at=datetime.fromisoformat(node["created_at"]),
                            valid_at=datetime.fromisoformat(node["valid_at"]),
                        )
                    )
                return entities
        except Exception as exc:
            raise MemoryBackendError("neo4j", str(exc)) from exc

    async def delete_entity(self, entity_id: str) -> None:
        """Soft-delete by setting expired_at (preserves temporal history)."""
        driver = self._ensure_driver()
        now = datetime.now(UTC).isoformat()
        try:
            with driver.session() as session:
                session.run(
                    "MATCH (n:Entity {id: $id}) SET n.expired_at = $expired_at",
                    id=entity_id,
                    expired_at=now,
                )
        except Exception as exc:
            raise MemoryBackendError("neo4j", str(exc)) from exc

        logger.info("kg_entity_soft_deleted", entity_id=entity_id)
