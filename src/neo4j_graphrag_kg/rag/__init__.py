"""RAG query pipeline: natural language → Cypher → answer."""

from neo4j_graphrag_kg.rag.pipeline import ask, RAGResponse

__all__ = ["ask", "RAGResponse"]
