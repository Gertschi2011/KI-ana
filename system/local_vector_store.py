"""
Local Vector Store with Qdrant + Local Embeddings

Combines local embeddings with Qdrant for fully local vector search.
No OpenAI API needed!
"""
from __future__ import annotations
import time
import os
from typing import List, Dict, Any, Optional
from dataclasses import dataclass
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, VectorParams, PointStruct, Filter, FieldCondition, MatchValue
import sys
from pathlib import Path

# Import local embeddings
sys.path.insert(0, str(Path.home() / "ki_ana" / "system"))
from local_embeddings import get_embedding_service


@dataclass
class SearchResult:
    """Result from vector search."""
    id: str
    score: float
    payload: Dict[str, Any]
    text: Optional[str] = None


class LocalVectorStore:
    """
    Local vector store using Qdrant + local embeddings.
    
    Fully local, no cloud APIs needed!
    """
    
    _instance: Optional['LocalVectorStore'] = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self):
        if hasattr(self, '_initialized'):
            return
        
        self._initialized = True
        
        # Qdrant connection
        self.qdrant_host = os.getenv("QDRANT_HOST", "127.0.0.1")
        self.qdrant_port = int(os.getenv("QDRANT_PORT", "6333"))
        
        self.client = QdrantClient(host=self.qdrant_host, port=self.qdrant_port)
        
        # Embedding service
        self.embedding_service = get_embedding_service()
        
        # Default collection name
        self.default_collection = "kiana_local"
        
        print(f"✅ Local Vector Store initialized (Qdrant: {self.qdrant_host}:{self.qdrant_port})")
    
    def create_collection(
        self,
        collection_name: str = None,
        dimension: int = 384,  # mini model default
        distance: str = "Cosine",
        recreate: bool = False
    ) -> bool:
        """
        Create a new collection for vectors.
        
        Args:
            collection_name: Name of collection (default: kiana_local)
            dimension: Vector dimension (384 for mini, 768 for base/multilingual)
            distance: Distance metric (Cosine, Euclid, Dot)
            recreate: If True, delete existing collection first
        
        Returns:
            True if created successfully
        """
        collection_name = collection_name or self.default_collection
        
        # Check if exists
        collections = self.client.get_collections().collections
        exists = any(c.name == collection_name for c in collections)
        
        if exists:
            if recreate:
                print(f"🗑️  Deleting existing collection: {collection_name}")
                self.client.delete_collection(collection_name)
            else:
                print(f"✅ Collection already exists: {collection_name}")
                return True
        
        # Create collection
        print(f"📦 Creating collection: {collection_name} ({dimension}d, {distance})")
        
        self.client.create_collection(
            collection_name=collection_name,
            vectors_config=VectorParams(
                size=dimension,
                distance=Distance[distance.upper()]
            )
        )
        
        print(f"✅ Collection created: {collection_name}")
        return True
    
    def add_texts(
        self,
        texts: List[str],
        metadatas: Optional[List[Dict[str, Any]]] = None,
        ids: Optional[List[str]] = None,
        collection_name: str = None,
        model: str = None,
        batch_size: int = 100
    ) -> List[str]:
        """
        Add texts to vector store with local embeddings.
        
        Args:
            texts: List of texts to add
            metadatas: Optional metadata for each text
            ids: Optional IDs (auto-generated if not provided)
            collection_name: Collection to add to
            model: Embedding model to use
            batch_size: Batch size for processing
        
        Returns:
            List of IDs
        """
        collection_name = collection_name or self.default_collection
        
        if not texts:
            return []
        
        # Generate IDs if not provided
        if ids is None:
            import uuid
            ids = [str(uuid.uuid4()) for _ in texts]
        
        # Prepare metadata
        if metadatas is None:
            metadatas = [{} for _ in texts]
        
        # Generate embeddings locally
        print(f"🔤 Generating {len(texts)} embeddings locally...")
        start = time.time()
        
        embedding_results = self.embedding_service.embed_batch(
            texts=texts,
            model=model,
            batch_size=batch_size
        )
        
        embeddings = [r.embedding for r in embedding_results]
        embed_time = time.time() - start
        
        print(f"✅ Embeddings generated in {embed_time:.2f}s ({len(texts)/embed_time:.1f} texts/s)")
        
        # Prepare points for Qdrant
        points = []
        for i, (text, embedding, metadata, point_id) in enumerate(zip(texts, embeddings, metadatas, ids)):
            payload = {
                "text": text,
                **metadata
            }
            
            points.append(PointStruct(
                id=point_id,
                vector=embedding,
                payload=payload
            ))
        
        # Upload to Qdrant in batches
        print(f"📤 Uploading {len(points)} points to Qdrant...")
        start = time.time()
        
        for i in range(0, len(points), batch_size):
            batch = points[i:i+batch_size]
            self.client.upsert(
                collection_name=collection_name,
                points=batch
            )
        
        upload_time = time.time() - start
        print(f"✅ Upload complete in {upload_time:.2f}s")
        
        return ids
    
    def search(
        self,
        query: str,
        collection_name: str = None,
        limit: int = 5,
        score_threshold: float = 0.0,
        filter_dict: Optional[Dict[str, Any]] = None,
        model: str = None
    ) -> List[SearchResult]:
        """
        Search for similar texts using local embeddings.
        
        Args:
            query: Search query
            collection_name: Collection to search in
            limit: Maximum number of results
            score_threshold: Minimum similarity score
            filter_dict: Optional metadata filters
            model: Embedding model to use
        
        Returns:
            List of SearchResult objects
        """
        collection_name = collection_name or self.default_collection
        
        # Generate query embedding locally
        query_result = self.embedding_service.embed(query, model=model)
        query_vector = query_result.embedding
        
        # Prepare filter
        query_filter = None
        if filter_dict:
            conditions = []
            for key, value in filter_dict.items():
                conditions.append(
                    FieldCondition(
                        key=key,
                        match=MatchValue(value=value)
                    )
                )
            if conditions:
                query_filter = Filter(must=conditions)
        
        # Search in Qdrant
        search_results = self.client.search(
            collection_name=collection_name,
            query_vector=query_vector,
            limit=limit,
            score_threshold=score_threshold,
            query_filter=query_filter
        )
        
        # Convert to SearchResult objects
        results = []
        for hit in search_results:
            results.append(SearchResult(
                id=str(hit.id),
                score=hit.score,
                payload=hit.payload,
                text=hit.payload.get("text")
            ))
        
        return results
    
    def get_collection_info(self, collection_name: str = None) -> Dict[str, Any]:
        """Get information about a collection."""
        collection_name = collection_name or self.default_collection
        
        try:
            info = self.client.get_collection(collection_name)
            
            return {
                "name": collection_name,
                "vectors_count": info.vectors_count,
                "points_count": info.points_count,
                "status": info.status,
                "config": {
                    "dimension": info.config.params.vectors.size,
                    "distance": info.config.params.vectors.distance.name
                }
            }
        except Exception as e:
            return {
                "name": collection_name,
                "error": str(e),
                "exists": False
            }
    
    def list_collections(self) -> List[str]:
        """List all collections."""
        collections = self.client.get_collections().collections
        return [c.name for c in collections]
    
    def delete_collection(self, collection_name: str) -> bool:
        """Delete a collection."""
        try:
            self.client.delete_collection(collection_name)
            print(f"🗑️  Deleted collection: {collection_name}")
            return True
        except Exception as e:
            print(f"❌ Error deleting collection: {e}")
            return False
    
    def count(self, collection_name: str = None) -> int:
        """Count points in collection."""
        collection_name = collection_name or self.default_collection
        
        try:
            info = self.client.get_collection(collection_name)
            return info.points_count or 0
        except:
            return 0


# Singleton instance
_store: Optional[LocalVectorStore] = None


def get_vector_store() -> LocalVectorStore:
    """Get the singleton vector store instance."""
    global _store
    if _store is None:
        _store = LocalVectorStore()
    return _store


if __name__ == "__main__":
    # Quick test
    print("🔍 Local Vector Store Test\n")
    
    store = get_vector_store()
    
    # List collections
    print("📋 Existing collections:")
    collections = store.list_collections()
    for col in collections:
        print(f"  - {col}")
    
    # Create test collection
    print("\n📦 Creating test collection...")
    store.create_collection("test_local", dimension=384, recreate=True)
    
    # Add test data
    print("\n📝 Adding test data...")
    texts = [
        "KI_ana ist ein intelligenter Assistent mit lokalen Modellen.",
        "Der Assistent läuft vollständig offline ohne Cloud.",
        "Lokale Embeddings sind schneller und privater.",
        "Pizza ist ein italienisches Gericht mit Tomaten und Käse.",
        "Python ist eine beliebte Programmiersprache."
    ]
    
    ids = store.add_texts(
        texts=texts,
        metadatas=[{"category": "ai"}, {"category": "ai"}, {"category": "ai"}, {"category": "food"}, {"category": "tech"}],
        collection_name="test_local"
    )
    
    print(f"✅ Added {len(ids)} texts")
    
    # Search
    print("\n🔍 Searching...")
    query = "Wie funktioniert der KI-Assistent?"
    results = store.search(query, collection_name="test_local", limit=3)
    
    print(f"\nQuery: '{query}'")
    print(f"Results:")
    for i, result in enumerate(results, 1):
        print(f"  {i}. [{result.score:.3f}] {result.text}")
    
    # Filtered search
    print("\n🔍 Filtered search (category=ai)...")
    results = store.search(
        query,
        collection_name="test_local",
        limit=3,
        filter_dict={"category": "ai"}
    )
    
    print(f"Results (filtered):")
    for i, result in enumerate(results, 1):
        print(f"  {i}. [{result.score:.3f}] {result.text}")
    
    # Collection info
    print("\n📊 Collection info:")
    info = store.get_collection_info("test_local")
    print(f"  Points: {info['points_count']}")
    print(f"  Dimension: {info['config']['dimension']}")
    print(f"  Distance: {info['config']['distance']}")
    
    # Cleanup
    print("\n🗑️  Cleaning up...")
    store.delete_collection("test_local")
    
    print("\n✅ Test complete!")
