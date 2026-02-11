"""
End-to-end test script for Multi-tenant RAG System
Tests the complete flow: create tenant -> ingest document -> query -> verify caching
"""
import asyncio
import httpx
import uuid
from sqlalchemy import text
from database import AsyncSessionLocal, engine


BASE_URL = "http://localhost:8000"


async def create_test_tenant():
    """Create a test tenant in the database"""
    async with AsyncSessionLocal() as session:
        tenant_id = uuid.uuid4()
        query = text("INSERT INTO tenants (id, name) VALUES (:id, :name)")
        await session.execute(query, {"id": str(tenant_id), "name": "Test Tenant"})
        await session.commit()
        print(f"✓ Created test tenant: {tenant_id}")
        return tenant_id


async def test_ingest(tenant_id: uuid.UUID):
    """Test document ingestion"""
    print("\n--- Testing Document Ingestion ---")
    
    document_content = """
    Artificial Intelligence (AI) is transforming the world. Machine learning, a subset of AI,
    enables computers to learn from data without explicit programming. Deep learning uses neural
    networks with multiple layers to process complex patterns. Natural Language Processing (NLP)
    allows machines to understand and generate human language. Computer vision enables machines
    to interpret visual information from the world.
    """
    
    async with httpx.AsyncClient() as client:
        response = await client.post(
            f"{BASE_URL}/ingest",
            json={
                "tenant_id": str(tenant_id),
                "content": document_content,
                "metadata": {
                    "title": "Introduction to AI",
                    "source": "test_script"
                }
            },
            timeout=30.0
        )
        
        if response.status_code == 201:
            data = response.json()
            print(f"✓ Document ingested successfully")
            print(f"  - Document ID: {data['document_id']}")
            print(f"  - Chunks created: {data['chunks_created']}")
            return data['document_id']
        else:
            print(f"✗ Ingestion failed: {response.status_code}")
            print(f"  Response: {response.text}")
            return None


async def test_query(tenant_id: uuid.UUID, query_text: str, expected_cached: bool = False):
    """Test query endpoint"""
    print(f"\n--- Testing Query (cached={expected_cached}) ---")
    print(f"Query: {query_text}")
    
    async with httpx.AsyncClient() as client:
        response = await client.post(
            f"{BASE_URL}/query",
            json={
                "tenant_id": str(tenant_id),
                "query": query_text,
                "top_k": 3
            },
            timeout=30.0
        )
        
        if response.status_code == 200:
            data = response.json()
            print(f"✓ Query successful")
            print(f"  - Cached: {data['cached']}")
            print(f"  - Answer: {data['answer'][:200]}...")
            print(f"  - Sources found: {len(data['sources'])}")
            
            if data['sources']:
                print(f"  - Top source similarity: {data['sources'][0]['similarity_score']:.3f}")
            
            # Verify caching behavior
            if data['cached'] == expected_cached:
                print(f"✓ Cache behavior correct (expected cached={expected_cached})")
            else:
                print(f"✗ Cache behavior incorrect (expected cached={expected_cached}, got {data['cached']})")
            
            return data
        else:
            print(f"✗ Query failed: {response.status_code}")
            print(f"  Response: {response.text}")
            return None


async def test_tenant_isolation(tenant_id: uuid.UUID, other_tenant_id: uuid.UUID):
    """Test that tenant isolation works"""
    print("\n--- Testing Tenant Isolation ---")
    
    # Query with different tenant should return no results or refuse to answer
    async with httpx.AsyncClient() as client:
        response = await client.post(
            f"{BASE_URL}/query",
            json={
                "tenant_id": str(other_tenant_id),
                "query": "What is machine learning?",
                "top_k": 3
            },
            timeout=30.0
        )
        
        if response.status_code == 200:
            data = response.json()
            if "cannot answer" in data['answer'].lower() or len(data['sources']) == 0:
                print(f"✓ Tenant isolation working correctly")
                print(f"  - Other tenant got: {data['answer'][:100]}...")
            else:
                print(f"✗ Tenant isolation may be broken - other tenant got results")
        else:
            print(f"✗ Query failed: {response.status_code}")


async def test_health():
    """Test health endpoint"""
    print("\n--- Testing Health Endpoint ---")
    
    async with httpx.AsyncClient() as client:
        response = await client.get(f"{BASE_URL}/health", timeout=5.0)
        
        if response.status_code == 200:
            data = response.json()
            print(f"✓ Health check passed: {data}")
        else:
            print(f"✗ Health check failed: {response.status_code}")


async def cleanup_test_data(tenant_id: uuid.UUID):
    """Clean up test data"""
    print("\n--- Cleaning up test data ---")
    async with AsyncSessionLocal() as session:
        # Delete tenant (cascade will delete all related data)
        query = text("DELETE FROM tenants WHERE id = :id")
        await session.execute(query, {"id": str(tenant_id)})
        await session.commit()
        print(f"✓ Cleaned up test tenant: {tenant_id}")


async def main():
    """Run all tests"""
    print("=" * 60)
    print("Multi-tenant RAG System - End-to-End Test")
    print("=" * 60)
    
    try:
        # Test health
        await test_health()
        
        # Create test tenant
        tenant_id = await create_test_tenant()
        
        # Create another tenant for isolation testing
        other_tenant_id = await create_test_tenant()
        
        # Test ingestion
        document_id = await test_ingest(tenant_id)
        
        if document_id:
            # Wait a moment for indexing
            await asyncio.sleep(2)
            
            # Test query (first time - should not be cached)
            await test_query(tenant_id, "What is machine learning?", expected_cached=False)
            
            # Test query (second time - should be cached)
            await test_query(tenant_id, "What is machine learning?", expected_cached=True)
            
            # Test different query
            await test_query(tenant_id, "Explain deep learning", expected_cached=False)
            
            # Test tenant isolation
            await test_tenant_isolation(tenant_id, other_tenant_id)
        
        # Cleanup
        await cleanup_test_data(tenant_id)
        await cleanup_test_data(other_tenant_id)
        
        print("\n" + "=" * 60)
        print("✓ All tests completed!")
        print("=" * 60)
    
    except Exception as e:
        print(f"\n✗ Test failed with error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())
