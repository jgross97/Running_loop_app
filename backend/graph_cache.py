import os
import pickle
import time
from pathlib import Path
from typing import Optional, Tuple
import networkx as nx

CACHE_DIR = Path("./graph_cache")
CACHE_EXPIRY = 30 * 24 * 60 * 60  # 30 days in seconds

class GraphCache:
    """
    Persistent graph cache that can easily be replaced with a database implementation.
    This class abstracts the caching mechanism to make future database migration simple.
    """
    
    def __init__(self, cache_dir: str = "./graph_cache", expiry_seconds: int = CACHE_EXPIRY):
        self.cache_dir = Path(cache_dir)
        self.expiry_seconds = expiry_seconds
        self.init_cache()
    
    def init_cache(self):
        """Initialize cache directory"""
        os.makedirs(self.cache_dir, exist_ok=True)
    
    def get_cache_key(self, center: Tuple[float, float], dist: int) -> str:
        """Generate cache key for graph"""
        lat, lon = center
        return f"graph_{lat:.5f}_{lon:.5f}_{dist}"
    
    def save_graph(self, G: nx.Graph, center: Tuple[float, float], dist: int):
        """Save graph to persistent storage"""
        cache_key = self.get_cache_key(center, dist)
        cache_path = self.cache_dir / f"{cache_key}.pkl"
        
        cache_data = {
            'graph': G,
            'timestamp': time.time(),
            'center': center,
            'dist': dist
        }
        
        try:
            with open(cache_path, 'wb') as f:
                pickle.dump(cache_data, f)
            print(f"Graph saved to cache: {cache_key}")
        except Exception as e:
            print(f"Failed to save graph to cache: {e}")
    
    def load_graph(self, center: Tuple[float, float], dist: int) -> Optional[nx.Graph]:
        """Load graph from persistent storage"""
        cache_key = self.get_cache_key(center, dist)
        cache_path = self.cache_dir / f"{cache_key}.pkl"
        
        if not cache_path.exists():
            return None
        
        try:
            with open(cache_path, 'rb') as f:
                cached = pickle.load(f)
            
            # Check if cache is expired
            if time.time() - cached['timestamp'] > self.expiry_seconds:
                print(f"Cache expired for {cache_key}")
                return None
            
            print(f"Graph loaded from disk cache: {cache_key}")
            return cached['graph']
            
        except Exception as e:
            print(f"Failed to load graph from cache: {e}")
            return None
    
    def clear_expired(self):
        """Remove expired cache files"""
        current_time = time.time()
        for cache_file in self.cache_dir.glob("*.pkl"):
            try:
                with open(cache_file, 'rb') as f:
                    cached = pickle.load(f)
                if current_time - cached['timestamp'] > self.expiry_seconds:
                    cache_file.unlink()
                    print(f"Removed expired cache: {cache_file.name}")
            except Exception:
                # If we can't read the file, it's probably corrupted, so delete it
                cache_file.unlink()

# Global cache instance
graph_cache = GraphCache()
