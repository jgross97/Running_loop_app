import requests
import time
from typing import List, Tuple, Optional

def get_elevation_data(coordinates: List[Tuple[float, float]], batch_size: int = 100) -> List[Optional[float]]:
    """
    Get elevation data for a list of coordinates using Open Elevation API.
    
    Args:
        coordinates: List of (lat, lon) tuples
        batch_size: Number of coordinates to process in each API call
        
    Returns:
        List of elevation values in meters (None if unavailable)
    """
    elevations = []
    
    # Process coordinates in batches to avoid API limits
    for i in range(0, len(coordinates), batch_size):
        batch = coordinates[i:i + batch_size]
        batch_elevations = _get_batch_elevations(batch)
        elevations.extend(batch_elevations)
        
        # Add small delay between batches to be respectful to the API
        if i + batch_size < len(coordinates):
            time.sleep(0.1)
    
    return elevations

def _get_batch_elevations(coordinates: List[Tuple[float, float]]) -> List[Optional[float]]:
    """Get elevations for a batch of coordinates using Open Elevation API."""
    try:
        # Prepare locations for Open Elevation API
        locations = [{"latitude": lat, "longitude": lon} for lat, lon in coordinates]
        
        response = requests.post(
            "https://api.open-elevation.com/api/v1/lookup",
            json={"locations": locations},
            timeout=30
        )
        
        if response.status_code == 200:
            data = response.json()
            return [result["elevation"] for result in data["results"]]
        else:
            print(f"Elevation API error: {response.status_code}")
            return [None] * len(coordinates)
            
    except Exception as e:
        print(f"Error fetching elevation data: {e}")
        return [None] * len(coordinates)

def calculate_elevation_gain(elevations: List[Optional[float]]) -> Tuple[float, float]:
    """
    Calculate total elevation gain and loss from elevation profile.
    
    Args:
        elevations: List of elevation values in meters
        
    Returns:
        Tuple of (total_gain, total_loss) in meters
    """
    if not elevations or len(elevations) < 2:
        return 0.0, 0.0
    
    # Filter out None values and smooth the data
    valid_elevations = [e for e in elevations if e is not None]
    
    if len(valid_elevations) < 2:
        return 0.0, 0.0
    
    # Simple smoothing to reduce GPS noise
    smoothed = smooth_elevations(valid_elevations)
    
    total_gain = 0.0
    total_loss = 0.0
    
    for i in range(1, len(smoothed)):
        diff = smoothed[i] - smoothed[i-1]
        if diff > 0:
            total_gain += diff
        else:
            total_loss += abs(diff)
    
    return total_gain, total_loss

def smooth_elevations(elevations: List[float], window_size: int = 3) -> List[float]:
    """Apply simple moving average to smooth elevation data."""
    if len(elevations) <= window_size:
        return elevations
    
    smoothed = []
    half_window = window_size // 2
    
    for i in range(len(elevations)):
        start = max(0, i - half_window)
        end = min(len(elevations), i + half_window + 1)
        avg = sum(elevations[start:end]) / (end - start)
        smoothed.append(avg)
    
    return smoothed

def get_route_elevation_profile(G, path: List, sample_rate: int = 10) -> dict:
    """
    Get complete elevation profile for a route path.
    
    Args:
        G: NetworkX graph
        path: List of node IDs representing the route
        sample_rate: Take every Nth node to reduce API calls
        
    Returns:
        Dictionary with elevation gain, loss, and profile data
    """
    if not path or len(path) < 2:
        return {
            "elevation_gain": 0.0,
            "elevation_loss": 0.0,
            "max_elevation": None,
            "min_elevation": None,
            "elevation_profile": [],
            "smoothed_elevation_profile": []
        }
    
    # Sample nodes to reduce API calls while maintaining accuracy
    sampled_nodes = path[::sample_rate]
    if path[-1] not in sampled_nodes:
        sampled_nodes.append(path[-1])  # Always include the end point
    
    # Get coordinates for sampled nodes
    coordinates = [(G.nodes[node]['y'], G.nodes[node]['x']) for node in sampled_nodes]
    
    # Get elevation data
    elevations = get_elevation_data(coordinates)
    
    # Calculate gains and losses
    elevation_gain, elevation_loss = calculate_elevation_gain(elevations)
    
    # Calculate min/max elevations and get smoothed elevations
    valid_elevations = [e for e in elevations if e is not None]
    smoothed_elevations = smooth_elevations(valid_elevations) if len(valid_elevations) >= 2 else valid_elevations
    max_elevation = max(valid_elevations) if valid_elevations else None
    min_elevation = min(valid_elevations) if valid_elevations else None
    
    return {
        "elevation_gain": round(elevation_gain, 1),
        "elevation_loss": round(elevation_loss, 1),
        # Handle 0-meter elevations correctly by explicitly checking for None
        "max_elevation": round(max_elevation, 1) if max_elevation is not None else None,
        "min_elevation": round(min_elevation, 1) if min_elevation is not None else None,
        "elevation_profile": elevations,
        "smoothed_elevation_profile": [round(e, 1) for e in smoothed_elevations] if smoothed_elevations else []
    }
