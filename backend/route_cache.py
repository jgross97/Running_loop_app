import hashlib
import json
import os
import time
from pathlib import Path
from typing import Optional, Dict, Any

ROUTES_CACHE_DIR = Path("./routes_cache")
ROUTES_CACHE_EXPIRY = 7 * 24 * 60 * 60  # 7 days in seconds

class RouteCache:
    """
    Persistent route cache that can easily be replaced with a database implementation.
    This class abstracts the caching mechanism to make future database migration simple.
    """
    
    def __init__(self, cache_dir: str = "./routes_cache", expiry_seconds: int = ROUTES_CACHE_EXPIRY):
        self.cache_dir = Path(cache_dir)
        self.expiry_seconds = expiry_seconds
        self.init_cache()
    
    def init_cache(self):
        """Initialize cache directory"""
        os.makedirs(self.cache_dir, exist_ok=True)
    
    def get_route_cache_key(self, start_lat: float, start_lon: float, 
                           end_lat: float, end_lon: float, distance_miles: float) -> str:
        """Generate cache key for route"""
        # Round coordinates to reduce cache misses for nearby points
        data = f"{start_lat:.5f}_{start_lon:.5f}_{end_lat:.5f}_{end_lon:.5f}_{distance_miles:.2f}"
        return hashlib.md5(data.encode()).hexdigest()
    
    def save_route(self, route_data: Dict[str, Any], start_lat: float, start_lon: float,
                   end_lat: float, end_lon: float, distance_miles: float):
        """Save route to persistent storage"""
        cache_key = self.get_route_cache_key(start_lat, start_lon, end_lat, end_lon, distance_miles)
        cache_path = self.cache_dir / f"{cache_key}.json"
        
        cache_data = {
            'route_data': route_data,
            'timestamp': time.time(),
            'params': {
                'start_lat': start_lat,
                'start_lon': start_lon,
                'end_lat': end_lat,
                'end_lon': end_lon,
                'distance_miles': distance_miles
            }
        }
        
        try:
            with open(cache_path, 'w') as f:
                json.dump(cache_data, f)
            print(f"Route saved to cache: {cache_key}")
        except Exception as e:
            print(f"Failed to save route to cache: {e}")
    
    def load_route(self, start_lat: float, start_lon: float,
                   end_lat: float, end_lon: float, distance_miles: float) -> Optional[Dict[str, Any]]:
        """Load route from persistent storage"""
        cache_key = self.get_route_cache_key(start_lat, start_lon, end_lat, end_lon, distance_miles)
        cache_path = self.cache_dir / f"{cache_key}.json"
        
        if not cache_path.exists():
            return None
        
        try:
            with open(cache_path, 'r') as f:
                cached = json.load(f)
            
            # Check if cache is expired
            if time.time() - cached['timestamp'] > self.expiry_seconds:
                print(f"Route cache expired for {cache_key}")
                return None
            
            print(f"Route loaded from cache: {cache_key}")
            return cached['route_data']
            
        except Exception as e:
            print(f"Failed to load route from cache: {e}")
            return None
    
    def clear_expired(self):
        """Remove expired cache files"""
        current_time = time.time()
        for cache_file in self.cache_dir.glob("*.json"):
            try:
                with open(cache_file, 'r') as f:
                    cached = json.load(f)
                if current_time - cached['timestamp'] > self.expiry_seconds:
                    cache_file.unlink()
                    print(f"Removed expired route cache: {cache_file.name}")
            except Exception:
                # If we can't read the file, it's probably corrupted, so delete it
                cache_file.unlink()

# Global cache instance
route_cache = RouteCache()
