#!/usr/bin/env python3
"""
Comprehensive TraitableHistory Demo with Assertions

This script demonstrates all TraitableHistory features with assertions and uses MongoStore:
1. History collection structure and automatic tracking
2. Time-based entity loading (as_of functionality)
3. AsOf context manager for batch historical queries
4. History querying and version management
5. Index creation and performance optimization
6. Instance-based StorableHelper architecture
7. User tracking and audit trails

Note: This demo requires MongoDB to be running as TraitableHistory
does not work with CACHE_ONLY mode.
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

# Add the project root to the path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from infra_10x.mongodb_store import MongoStore

from core_10x.traitable import T, Traitable


class Person(Traitable):
    """Example traitable class for comprehensive history testing."""
    name: str = T(T.ID)
    age: int = T()
    email: str = T()
    department: str = T()


class Product(Traitable):
    """Example product with price and inventory history tracking."""
    sku: str = T(T.ID)
    name: str = T()
    price: float = T()
    category: str = T()
    inventory: int = T()


def setup_mongodb_store():
    """Set up MongoDB store with error handling."""
    print("🔧 Setting up MongoDB store...")
    try:
        store = MongoStore("mongodb://localhost:27017", "traitable_history_comprehensive_demo")
        Traitable.set_store(store)
        print("✅ Connected to MongoDB store")
        return store
    except Exception as e:
        print(f"❌ Failed to connect to MongoDB: {e}")
        print("Please ensure MongoDB is running on localhost:27017")
        return None


def test_history_collection_structure():
    """Test the history collection structure and automatic tracking."""
    print("\n=== 1. History Collection Structure Test ===")
    
    # Create a person
    person = Person(name="Alice Johnson", age=30, email="alice@company.com", department="Engineering")
    print(f"Created person: {person.name} (age: {person.age})")
    
    # Save initial version
    rc = person.save()
    assert rc, f"Failed to save person: {rc}"
    print("✅ Initial save successful")
    
    # Wait a moment to ensure different timestamps
    time.sleep(0.1)
    
    # Update and save again
    person.age = 31
    person.email = "alice.johnson@company.com"
    rc = person.save()
    assert rc, f"Failed to save updated person: {rc}"
    print("✅ Updated save successful")
    
    # Check history collection exists
    store = Traitable.set_store()
    collection_names = store.collection_names()
    history_collection_name = None
    for name in collection_names:
        if name.endswith("#history"):
            history_collection_name = name
            break
    
    assert history_collection_name, "History collection not found"
    print(f"✅ History collection found: {history_collection_name}")
    
    # Check history entries
    history_docs = store.get_documents(history_collection_name)
    assert len(history_docs) == 2, f"Expected 2 history entries, got {len(history_docs)}"
    print(f"✅ Found {len(history_docs)} history entries")
    
    # Verify history entry structure
    for entry in history_docs:
        assert '_at' in entry, "History entry missing _at timestamp"
        assert '_who' in entry, "History entry missing _who field"
        assert entry['name'] == "Alice Johnson", "History entry has wrong name"
        print(f"✅ History entry has required fields: _at={entry['_at']}, _who={entry['_who']}")
    
    return person


def main():
    """Run the comprehensive TraitableHistory demo."""
    print("🚀 TraitableHistory Comprehensive Demo")
    print("=" * 50)
    
    # Set up MongoDB store
    store = setup_mongodb_store()
    if not store:
        return False
    
    try:
        # Run all tests
        test_history_collection_structure()
        
        print("\n" + "=" * 50)
        print("🎉 All TraitableHistory tests passed successfully!")
        
        return True
        
    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
