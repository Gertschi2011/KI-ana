"""
ChromaDB Vector Store with Local Embeddings

Fully embedded vector database - no external services needed!
Uses ChromaDB in persistent mode with local sentence-transformers embeddings.
"""
from __future__ import annotations
import time
import os
from pathlib import Path
from typing import List, Dict, Any, Optional
from dataclasses import dataclass
import sys

# Import local embeddings
sys.path.insert(0, str(Path.home() / "ki_ana" / "system"))
from local_embeddings import get_embedding_service

try:
    import chromadb
    from chromadb.config import Settings
    CHROMA_AVAILABLE = True
except ImportError:
    CHROMA_AVAILABLE = False
    print("⚠️  ChromaDB not available. Install with: pip install chromadb")


@dataclass
class SearchResult:
    """Result from vector search."""
    id: str
    score: float
    metadata: Dict[str, Any]
    text: Optional[str] = None


class ChromaVectorStore:
    """
    Embedded vector store using ChromaDB + local embeddings.
    
    Fully local, no external services!
    """
    
    _instance: Optional['ChromaVectorStore'] = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self):
        if hasattr(self, '_initialized'):
            return
        
        if not CHROMA_AVAILABLE:
            print("❌ ChromaDB not available")
            self._initialized = True
            return
        
        self._initialized = True
        
        # ChromaDB persistent directory
        self.chroma_dir = Path.home() / "ki_ana" / "data" / "chroma"
        self.chroma_dir.mkdir(parents=True, exist_ok=True)
        
        # Initialize ChromaDB client (persistent mode)
        self.client = chromadb.PersistentClient(
            path=str(self.chroma_dir),
            settings=Settings(
                anonymized_telemetry=False,
                allow_reset=True
            )
        )
        
        # Embedding service
        self.embedding_service = get_embedding_service()
        
        # Default collection name
        self.default_collection = "kiana_knowledge"
        
        print(f"✅ ChromaDB Vector Store initialized")
        print(f"   Path: {self.chroma_dir}")
    
    def _get_or_create_collection(self, collection_name: str = None):
        """Get or create a collection."""
        collection_name = collection_name or self.default_collection
        
        try:
            collection = self.client.get_collection(name=collection_name)
        except:
            # Create collection
            collection = self.client.create_collection(
                name=collection_name,
                metadata={"hnsw:space": "cosine"}  # Use cosine similarity
            )
            print(f"📦 Created collection: {collection_name}")
        
        return collection
    
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
        if not CHROMA_AVAILABLE:
            raise RuntimeError("ChromaDB not available")
        
        if not texts:
            return []
        
        collection = self._get_or_create_collection(collection_name)
        
        # Generate IDs if not provided
        if ids is None:
            import uuid
            ids = [str(uuid.uuid4()) for _ in texts]
        
        # Prepare metadata
        if metadatas is None:
            metadatas = [{} for _ in texts]
        
        # Add text to metadata
        for i, text in enumerate(texts):
            metadatas[i]["text"] = text
        
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
        
        # Add to ChromaDB in batches
        print(f"📤 Adding {len(texts)} documents to ChromaDB...")
        start = time.time()
        
        for i in range(0, len(texts), batch_size):
            batch_ids = ids[i:i+batch_size]
            batch_embeddings = embeddings[i:i+batch_size]
            batch_metadatas = metadatas[i:i+batch_size]
            
            collection.add(
                ids=batch_ids,
                embeddings=batch_embeddings,
                metadatas=batch_metadatas
            )
        
        add_time = time.time() - start
        print(f"✅ Added in {add_time:.2f}s")
        
        return ids
    
    def search(
        self,
        query: str,
        collection_name: str = None,
        limit: int = 5,
        where: Optional[Dict[str, Any]] = None,
        model: str = None
    ) -> List[SearchResult]:
        """
        Search for similar texts using local embeddings.
        
        Args:
            query: Search query
            collection_name: Collection to search in
            limit: Maximum number of results
            where: Optional metadata filters
            model: Embedding model to use
        
        Returns:
            List of SearchResult objects
        """
        if not CHROMA_AVAILABLE:
            raise RuntimeError("ChromaDB not available")
        
        collection = self._get_or_create_collection(collection_name)
        
        # Generate query embedding locally
        query_result = self.embedding_service.embed(query, model=model)
        query_embedding = query_result.embedding
        
        # Search in ChromaDB
        results = collection.query(
            query_embeddings=[query_embedding],
            n_results=limit,
            where=where
        )
        
        # Convert to SearchResult objects
        search_results = []
        
        if results['ids'] and results['ids'][0]:
            for i, doc_id in enumerate(results['ids'][0]):
                # ChromaDB returns distances, convert to similarity scores
                # For cosine: similarity = 1 - distance
                distance = results['distances'][0][i] if results['distances'] else 0
                score = 1 - distance
                
                metadata = results['metadatas'][0][i] if results['metadatas'] else {}
                text = metadata.pop('text', None)
                
                search_results.append(SearchResult(
                    id=doc_id,
                    score=score,
                    metadata=metadata,
                    text=text
                ))
        
        return search_results
    
    def get_collection_info(self, collection_name: str = None) -> Dict[str, Any]:
        """Get information about a collection."""
        collection_name = collection_name or self.default_collection
        
        try:
            collection = self.client.get_collection(name=collection_name)
            count = collection.count()
            
            return {
                "name": collection_name,
                "count": count,
                "exists": True
            }
        except Exception as e:
            return {
                "name": collection_name,
                "error": str(e),
                "exists": False
            }
    
    def list_collections(self) -> List[str]:
        """List all collections."""
        if not CHROMA_AVAILABLE:
            return []
        
        collections = self.client.list_collections()
        return [c.name for c in collections]
    
    def delete_collection(self, collection_name: str) -> bool:
        """Delete a collection."""
        if not CHROMA_AVAILABLE:
            return False
        
        try:
            self.client.delete_collection(name=collection_name)
            print(f"🗑️  Deleted collection: {collection_name}")
            return True
        except Exception as e:
            print(f"❌ Error deleting collection: {e}")
            return False
    
    def count(self, collection_name: str = None) -> int:
        """Count documents in collection."""
        collection_name = collection_name or self.default_collection
        
        try:
            collection = self.client.get_collection(name=collection_name)
            return collection.count()
        except:
            return 0


# Singleton instance
_store: Optional[ChromaVectorStore] = None


def get_chroma_store() -> ChromaVectorStore:
    """Get the singleton ChromaDB store instance."""
    global _store
    if _store is None:
        _store = ChromaVectorStore()
    return _store


if __name__ == "__main__":
    # Quick test
    print("🔍 ChromaDB Vector Store Test\n")
    
    if not CHROMA_AVAILABLE:
        print("❌ ChromaDB not installed. Install with:")
        print("   pip install chromadb")
        exit(1)
    
    store = get_chroma_store()
    
    # List collections
    print("📋 Existing collections:")
    collections = store.list_collections()
    for col in collections:
        print(f"  - {col}")
    
    # Create test collection
    print("\n📦 Creating test collection...")
    test_collection = "test_chroma"
    
    # Add test data
    print("\n📝 Adding test data...")
    texts = [
        "ChromaDB ist eine embedded Vector Database.",
        "Lokale Embeddings sind schnell und privat.",
        "KI_ana läuft vollständig offline.",
        "Pizza ist ein italienisches Gericht.",
        "Python ist eine Programmiersprache."
    ]
    
    metadatas = [
        {"category": "tech"},
        {"category": "tech"},
        {"category": "tech"},
        {"category": "food"},
        {"category": "tech"}
    ]
    
    ids = store.add_texts(
        texts=texts,
        metadatas=metadatas,
        collection_name=test_collection
    )
    
    print(f"✅ Added {len(ids)} texts")
    
    # Search
    print("\n🔍 Searching...")
    query = "Wie funktioniert die Vector Database?"
    results = store.search(query, collection_name=test_collection, limit=3)
    
    print(f"\nQuery: '{query}'")
    print(f"Results:")
    for i, result in enumerate(results, 1):
        print(f"  {i}. [{result.score:.3f}] {result.text}")
        print(f"     Category: {result.metadata.get('category')}")
    
    # Filtered search
    print("\n🔍 Filtered search (category=tech)...")
    results = store.search(
        query,
        collection_name=test_collection,
        limit=3,
        where={"category": "tech"}
    )
    
    print(f"Results (filtered):")
    for i, result in enumerate(results, 1):
        print(f"  {i}. [{result.score:.3f}] {result.text}")
    
    # Collection info
    print("\n📊 Collection info:")
    info = store.get_collection_info(test_collection)
    print(f"  Name: {info['name']}")
    print(f"  Count: {info['count']}")
    
    # Cleanup
    print("\n🗑️  Cleaning up...")
    store.delete_collection(test_collection)
    
    print("\n✅ Test complete!")
