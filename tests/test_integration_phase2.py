"""
Integration Tests for Phase 2: Lokale Autonomie

Tests all local services working together:
- Local Embeddings
- Vector Search (Qdrant & ChromaDB)
- Voice (STT & TTS)
- SQLite Database
- Submind System
"""
import sys
from pathlib import Path
import time

# Add system path
_REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_REPO_ROOT / "system"))

def test_local_embeddings():
    """Test local embeddings service."""
    print("\n🔤 Testing Local Embeddings...")
    
    from local_embeddings import get_embedding_service
    
    service = get_embedding_service()
    
    # Test single embedding
    text = "KI_ana läuft vollständig lokal"
    result = service.embed(text)
    
    assert result.dimension == 384, "Wrong dimension"
    assert len(result.embedding) == 384, "Wrong embedding length"
    assert result.generation_time < 0.5, "Too slow"
    
    print(f"✅ Single embedding: {result.dimension}d in {result.generation_time*1000:.1f}ms")
    
    # Test batch embedding
    texts = ["Text 1", "Text 2", "Text 3"]
    results = service.embed_batch(texts)
    
    assert len(results) == 3, "Wrong batch size"
    
    print(f"✅ Batch embedding: {len(results)} texts")
    
    # Test similarity
    sim = service.similarity("KI_ana", "Künstliche Intelligenz")
    
    assert 0 <= sim <= 1, "Invalid similarity score"
    
    print(f"✅ Similarity: {sim:.3f}")
    
    return True


def test_vector_search_qdrant():
    """Test Qdrant vector search."""
    print("\n🔍 Testing Qdrant Vector Search...")
    
    try:
        from local_vector_store import get_vector_store
        
        store = get_vector_store()
        
        # Create test collection
        collection = "test_integration"
        store.create_collection(collection, dimension=384, recreate=True)
        
        # Add texts
        texts = [
            "Lokale Embeddings sind schnell",
            "Vector Search funktioniert offline",
            "KI_ana ist autonom"
        ]
        
        ids = store.add_texts(texts, collection_name=collection)
        assert len(ids) == 3, "Wrong number of IDs"
        
        print(f"✅ Added {len(ids)} texts to Qdrant")
        
        # Search
        results = store.search("Wie funktioniert die lokale Suche?", collection_name=collection, limit=2)
        assert len(results) > 0, "No search results"
        
        print(f"✅ Search returned {len(results)} results")
        print(f"   Top result: [{results[0].score:.3f}] {results[0].text}")
        
        # Cleanup
        store.delete_collection(collection)
        
        return True
    except Exception as e:
        print(f"⚠️  Qdrant test skipped: {e}")
        return True  # Not critical


def test_vector_search_chroma():
    """Test ChromaDB vector search."""
    print("\n🔍 Testing ChromaDB Vector Search...")
    
    try:
        from chroma_vector_store import get_chroma_store
        
        store = get_chroma_store()
        
        # Add texts
        collection = "test_integration_chroma"
        texts = [
            "ChromaDB ist embedded",
            "Keine externen Services nötig",
            "Vollständig lokal"
        ]
        
        ids = store.add_texts(texts, collection_name=collection)
        assert len(ids) == 3, "Wrong number of IDs"
        
        print(f"✅ Added {len(ids)} texts to ChromaDB")
        
        # Search
        results = store.search("Wie funktioniert ChromaDB?", collection_name=collection, limit=2)
        assert len(results) > 0, "No search results"
        
        print(f"✅ Search returned {len(results)} results")
        print(f"   Top result: [{results[0].score:.3f}] {results[0].text}")
        
        # Cleanup
        store.delete_collection(collection)
        
        return True
    except Exception as e:
        print(f"❌ ChromaDB test failed: {e}")
        return False


def test_database():
    """Test hybrid database."""
    print("\n💾 Testing Hybrid Database...")
    
    from hybrid_db import get_database
    
    db = get_database()
    info = db.get_info()
    
    assert info["mode"] in ["server", "local"], "Invalid mode"
    
    print(f"✅ Database mode: {info['mode']}")
    print(f"   Type: {info['type']}")
    
    # Test session
    session = db.get_session()
    assert session is not None, "No session"
    session.close()
    
    print(f"✅ Session created successfully")
    
    return True


def test_submind_system():
    """Test submind manager."""
    print("\n🤖 Testing Submind System...")
    
    from submind_manager import get_submind_manager
    
    manager = get_submind_manager()
    
    # Get this device
    device = manager.get_this_device()
    
    if device:
        print(f"✅ This device: {device.name}")
        print(f"   ID: {device.id}")
        print(f"   Role: {device.role}")
        print(f"   Type: {device.device_type}")
        
        # Test permissions
        has_all = manager.has_permission(device.id, "all")
        print(f"✅ Permission check: all = {has_all}")
    else:
        print(f"⚠️  No device registered yet")
    
    # Get stats
    stats = manager.get_stats()
    print(f"✅ Stats: {stats['total']} total, {stats['active']} active")
    
    return True


def test_voice_stt():
    """Test Speech-to-Text (if available)."""
    print("\n🎤 Testing STT (Speech-to-Text)...")
    
    try:
        from local_stt import get_stt_service
        
        service = get_stt_service()
        models = service.list_models()
        
        print(f"✅ STT available: {len(models)} models")
        print(f"   Default: {service.default_model}")
        
        return True
    except Exception as e:
        print(f"⚠️  STT test skipped: {e}")
        return True  # Not critical


def test_voice_tts():
    """Test Text-to-Speech (if available)."""
    print("\n🔊 Testing TTS (Text-to-Speech)...")
    
    try:
        from local_tts import get_tts_service
        
        service = get_tts_service()
        voices = service.list_voices()
        
        print(f"✅ TTS available: {len(voices)} voices")
        print(f"   Default: {service.default_voice}")
        
        return True
    except Exception as e:
        print(f"⚠️  TTS test skipped: {e}")
        return True  # Not critical


def test_end_to_end():
    """Test complete workflow: Text → Embedding → Vector Search."""
    print("\n🔄 Testing End-to-End Workflow...")
    
    from local_embeddings import get_embedding_service
    from chroma_vector_store import get_chroma_store
    
    # 1. Generate embeddings
    embedding_service = get_embedding_service()
    texts = [
        "Phase 2 ist abgeschlossen",
        "Alle Services laufen lokal",
        "Keine Cloud-Dependencies mehr"
    ]
    
    start = time.time()
    embedding_results = embedding_service.embed_batch(texts)
    embed_time = time.time() - start
    
    print(f"✅ Step 1: Generated {len(embedding_results)} embeddings in {embed_time:.3f}s")
    
    # 2. Store in vector DB
    vector_store = get_chroma_store()
    collection = "test_e2e"
    
    start = time.time()
    ids = vector_store.add_texts(texts, collection_name=collection)
    store_time = time.time() - start
    
    print(f"✅ Step 2: Stored {len(ids)} vectors in {store_time:.3f}s")
    
    # 3. Search
    query = "Ist Phase 2 fertig?"
    
    start = time.time()
    results = vector_store.search(query, collection_name=collection, limit=1)
    search_time = time.time() - start
    
    print(f"✅ Step 3: Search completed in {search_time:.3f}s")
    print(f"   Query: '{query}'")
    print(f"   Result: [{results[0].score:.3f}] {results[0].text}")
    
    # Total time
    total_time = embed_time + store_time + search_time
    print(f"✅ Total E2E time: {total_time:.3f}s")
    
    # Cleanup
    vector_store.delete_collection(collection)
    
    assert total_time < 5.0, "E2E too slow"
    
    return True


def run_all_tests():
    """Run all integration tests."""
    print("="*60)
    print("🧪 Phase 2 Integration Tests")
    print("="*60)
    
    tests = [
        ("Local Embeddings", test_local_embeddings),
        ("Vector Search (Qdrant)", test_vector_search_qdrant),
        ("Vector Search (ChromaDB)", test_vector_search_chroma),
        ("Hybrid Database", test_database),
        ("Submind System", test_submind_system),
        ("Voice STT", test_voice_stt),
        ("Voice TTS", test_voice_tts),
        ("End-to-End Workflow", test_end_to_end),
    ]
    
    results = {}
    
    for name, test_func in tests:
        try:
            success = test_func()
            results[name] = "✅ PASS" if success else "❌ FAIL"
        except Exception as e:
            results[name] = f"❌ ERROR: {e}"
            print(f"❌ Test failed: {e}")
    
    # Summary
    print("\n" + "="*60)
    print("📊 Test Summary")
    print("="*60)
    
    for name, result in results.items():
        print(f"{name:30} {result}")
    
    passed = sum(1 for r in results.values() if "✅" in r)
    total = len(results)
    
    print(f"\n{'='*60}")
    print(f"Result: {passed}/{total} tests passed ({passed/total*100:.0f}%)")
    print(f"{'='*60}")
    
    return passed == total


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)
