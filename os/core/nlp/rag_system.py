"""
RAG System (Retrieval Augmented Generation)

Adds knowledge retrieval to LLM responses.
"""

from typing import List, Dict, Any, Optional
from loguru import logger
from pathlib import Path
import json


class Document:
    """A document in the knowledge base"""
    
    def __init__(self, content: str, metadata: Dict[str, Any]):
        self.content = content
        self.metadata = metadata
        self.id = metadata.get("id", "")


class RAGSystem:
    """
    RAG (Retrieval Augmented Generation) System
    
    Enhances LLM with knowledge retrieval:
    - Index documents
    - Semantic search
    - Context augmentation
    - Citation support
    """
    
    def __init__(self, knowledge_base_path: str = "~/.kiana_knowledge"):
        self.kb_path = Path(knowledge_base_path).expanduser()
        self.kb_path.mkdir(parents=True, exist_ok=True)
        
        self.documents: List[Document] = []
        self.embeddings: Optional[Any] = None  # TODO: Use ChromaDB or similar
        
        self.load_knowledge_base()
    
    def load_knowledge_base(self):
        """Load existing knowledge base"""
        kb_file = self.kb_path / "documents.json"
        
        if kb_file.exists():
            try:
                with open(kb_file, 'r') as f:
                    data = json.load(f)
                    
                for doc_data in data:
                    doc = Document(
                        content=doc_data["content"],
                        metadata=doc_data["metadata"]
                    )
                    self.documents.append(doc)
                
                logger.info(f"📚 Loaded {len(self.documents)} documents")
            except Exception as e:
                logger.error(f"Failed to load knowledge base: {e}")
    
    def save_knowledge_base(self):
        """Save knowledge base to disk"""
        kb_file = self.kb_path / "documents.json"
        
        try:
            data = [
                {
                    "content": doc.content,
                    "metadata": doc.metadata
                }
                for doc in self.documents
            ]
            
            with open(kb_file, 'w') as f:
                json.dump(data, f, indent=2)
                
            logger.debug("💾 Knowledge base saved")
        except Exception as e:
            logger.error(f"Failed to save knowledge base: {e}")
    
    def add_document(self, content: str, metadata: Dict[str, Any] = None):
        """Add document to knowledge base"""
        if metadata is None:
            metadata = {}
        
        metadata["id"] = f"doc_{len(self.documents)}"
        
        doc = Document(content, metadata)
        self.documents.append(doc)
        
        logger.info(f"📄 Added document: {metadata.get('title', 'Untitled')}")
        self.save_knowledge_base()
    
    def search(self, query: str, limit: int = 5) -> List[Document]:
        """
        Search knowledge base
        
        Args:
            query: Search query
            limit: Max results
            
        Returns:
            List of relevant documents
        """
        # Simple keyword search for now
        # TODO: Implement semantic search with embeddings
        
        query_lower = query.lower()
        results = []
        
        for doc in self.documents:
            if query_lower in doc.content.lower():
                results.append(doc)
                
                if len(results) >= limit:
                    break
        
        logger.debug(f"🔍 Found {len(results)} documents for query: {query}")
        return results
    
    async def augment_prompt(self, user_query: str, max_context_docs: int = 3) -> str:
        """
        Augment user query with relevant context
        
        Args:
            user_query: Original user query
            max_context_docs: Max documents to include
            
        Returns:
            Augmented prompt with context
        """
        # Search knowledge base
        relevant_docs = self.search(user_query, limit=max_context_docs)
        
        if not relevant_docs:
            return user_query
        
        # Build context
        context = "Relevant information from knowledge base:\n\n"
        
        for i, doc in enumerate(relevant_docs, 1):
            context += f"[{i}] {doc.content}\n\n"
        
        # Augmented prompt
        augmented = f"{context}\nUser query: {user_query}\n\nPlease answer based on the provided context."
        
        logger.info(f"📚 Augmented prompt with {len(relevant_docs)} documents")
        return augmented
    
    def get_stats(self) -> Dict[str, Any]:
        """Get knowledge base statistics"""
        return {
            "total_documents": len(self.documents),
            "kb_path": str(self.kb_path)
        }
    
    def clear_knowledge_base(self):
        """Clear all documents"""
        self.documents = []
        self.save_knowledge_base()
        logger.info("🗑️ Knowledge base cleared")


# Singleton
_rag_instance: Optional[RAGSystem] = None


def get_rag_system() -> RAGSystem:
    """Get or create RAG system singleton"""
    global _rag_instance
    
    if _rag_instance is None:
        _rag_instance = RAGSystem()
    
    return _rag_instance
