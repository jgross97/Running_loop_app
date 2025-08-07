#!/usr/bin/env python3
"""
Test script to verify the optimized caching system is working
"""

import sys
import time
from pathlib import Path

# Add the backend directory to the path so we can import our modules
sys.path.append(str(Path(__file__).parent))

from graph_cache import graph_cache
from route_cache import route_cache

def test_caches():
    """Test that caches initialize correctly"""
    print("Testing cache initialization...")
    
    # Test graph cache
    graph_cache.init_cache()
    print(f"Graph cache directory: {graph_cache.cache_dir}")
    print(f"Graph cache exists: {graph_cache.cache_dir.exists()}")
    
    # Test route cache
    route_cache.init_cache()
    print(f"Route cache directory: {route_cache.cache_dir}")
    print(f"Route cache exists: {route_cache.cache_dir.exists()}")
    
    print("Cache initialization test completed successfully!")

if __name__ == "__main__":
    test_caches()
