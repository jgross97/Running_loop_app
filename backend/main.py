
from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
from typing import List
import osmnx as ox
from concurrent.futures import ThreadPoolExecutor
from graph_cache import graph_cache
from route_cache import route_cache
from graph_utils import preprocess_graph
from elevation_utils import get_route_elevation_profile

ox.settings.use_cache = True
ox.settings.cache_folder = "osm_cache"

# Create a thread pool for background tasks
executor = ThreadPoolExecutor(max_workers=2)


# Multi-area graph cache
PRELOADED_DIST = 400
GRAPH_CACHE = {}

def round_coords(coords, precision=3):
    return tuple(round(c, precision) for c in coords)

def preload_graph(center, dist=PRELOADED_DIST):
    """
    Preload a graph for the given center point and distance.
    Optimized with persistent caching and background processing.
    """
    key = round_coords(center)
    
    # Cap the preload distance for efficiency
    MAX_PRELOAD_DIST = 5000  # meters
    effective_dist = min(dist, MAX_PRELOAD_DIST)
    
    # Check memory cache first
    if key in GRAPH_CACHE:
        print(f"Graph found in memory cache for {key}")
        return GRAPH_CACHE[key]
    
    # Check disk cache second
    disk_cached = graph_cache.load_graph(center, effective_dist)
    if disk_cached is not None:
        print(f"Graph loaded from disk cache for {key}")
        # Apply preprocessing to cached graph
        processed_graph = preprocess_graph(disk_cached)
        GRAPH_CACHE[key] = processed_graph
        return processed_graph
    
    # Download new graph if not cached
    print(f"Downloading new graph for {key} with dist={effective_dist}m (requested: {dist}m)")
    G = ox.graph_from_point(center, dist=effective_dist, network_type='walk')
    
    # Preprocess the graph for faster routing
    processed_graph = preprocess_graph(G)
    
    # Save to both memory and disk cache
    GRAPH_CACHE[key] = processed_graph
    graph_cache.save_graph(processed_graph, center, effective_dist)
    
    return processed_graph

app = FastAPI()

# Initialize caches and cleanup on startup
@app.on_event("startup")
async def startup_event():
    """Initialize caches and clean up expired entries"""
    graph_cache.init_cache()
    route_cache.init_cache()
    
    # Clean up expired cache entries
    graph_cache.clear_expired()
    route_cache.clear_expired()
    
    print("Cache system initialized and cleaned up")

# Preload default area on startup
preload_graph([40.0781, -75.2961], PRELOADED_DIST)

from fastapi import Body
@app.post("/preload")
def preload(payload: dict = Body(...)):
    center = payload.get("center")
    dist = payload.get("dist", PRELOADED_DIST)
    
    # Start preloading in background for non-blocking response
    executor.submit(preload_graph, center=center, dist=dist)
    
    return {"status": "preloading_started", "center": center, "dist": dist}

@app.post("/cache/clear")
def clear_cache():
    """Clear expired cache entries manually"""
    graph_cache.clear_expired()
    route_cache.clear_expired()
    return {"status": "cache_cleared"}

@app.get("/cache/status")
def cache_status():
    """Get cache status information"""
    memory_graphs = len(GRAPH_CACHE)
    return {
        "memory_graphs": memory_graphs,
        "cache_initialized": True
    }

# Allow CORS for local frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

import networkx as nx
from math import radians, sin, cos, sqrt, atan2, hypot
import math

def haversine_distance(lat1, lon1, lat2, lon2):
    """
    Calculate the great circle distance between two points on Earth in meters.
    Uses the Haversine formula for accurate distance calculation.
    """
    R = 6371000  # Earth radius in meters
    phi1, phi2 = radians(lat1), radians(lat2)
    dphi = radians(lat2 - lat1)
    dlambda = radians(lon2 - lon1)
    a = sin(dphi/2)**2 + cos(phi1)*cos(phi2)*sin(dlambda/2)**2
    c = 2 * atan2(sqrt(a), sqrt(1 - a))
    return R * c

def get_or_create_graph(start_lat, start_lon, end_lat, end_lon, dist):
    """
    Get an existing cached graph or create a new one for the given area.
    Returns the OSM graph for routing calculations.
    Optimized to reuse smaller graphs when possible and limit large downloads.
    """
    # Calculate the center point between start and end
    center_lat = (start_lat + end_lat) / 2
    center_lon = (start_lon + end_lon) / 2
    req_key = round_coords([center_lat, center_lon])
    # We'll store cache keys as (lat, lon, radius)
    
    # For efficiency, cap the maximum dist for graph creation
    # Very large areas take exponentially longer to download and process
    MAX_EFFICIENT_DIST = 150000  # meters
    effective_dist = min(dist, MAX_EFFICIENT_DIST)
    print(f"Fetching graph for {req_key} with effective distance: {effective_dist}m (requested: {dist}m)")
    
    # Try to find a nearby cached graph that could work
    closest_key = None
    min_dist = float('inf')
    best_cached_graph = None
    best_cached_radius = None
    # Now keys are (lat, lon, radius)
    for key in GRAPH_CACHE:
        # key: (lat, lon, radius)
        key_lat, key_lon, key_radius = key if len(key) == 3 else (key[0], key[1], None)
        d = hypot(req_key[0] - key_lat, req_key[1] - key_lon)
        print(f"Checking cached graph at ({key_lat}, {key_lon}, {key_radius}), distance: {d:.4f} degrees, radius: {key_radius}")
        # Only consider cached graphs whose radius is at least as large as requested
        if key_radius is not None and key_radius >= effective_dist:
            if d < min_dist:
                min_dist = d
                closest_key = key
                best_cached_graph = GRAPH_CACHE[key]
                best_cached_radius = key_radius
    # Use cached graph if it's close enough (within 0.01 degrees ≈ 1km)
    if (min_dist < 0.01 and closest_key is not None):
        print(f"Using cached graph at {closest_key}, distance: {min_dist:.4f} degrees, radius: {best_cached_radius}")
        return best_cached_graph
    else:
        # Create new graph with the effective (capped) distance
        print(f"Creating new graph for {req_key} with dist={effective_dist}m (requested: {dist}m)")
        G = ox.graph_from_point((center_lat, center_lon), dist=effective_dist, network_type='walk')
        
        # Preprocess the new graph for better performance
        processed_graph = preprocess_graph(G)
        # Store in cache with (lat, lon, radius)
        GRAPH_CACHE[(center_lat, center_lon, effective_dist)] = processed_graph
        # Save to disk cache for future use
        graph_cache.save_graph(processed_graph, (center_lat, center_lon), effective_dist)
        return processed_graph

def calculate_path_distance(G, path):
    """
    Calculate the total distance of a path using the Haversine formula.
    Returns distance in meters.
    """
    total_distance = 0
    for i in range(len(path) - 1):
        node1, node2 = path[i], path[i+1]
        lat1, lon1 = G.nodes[node1]['y'], G.nodes[node1]['x']
        lat2, lon2 = G.nodes[node2]['y'], G.nodes[node2]['x']
        total_distance += haversine_distance(lat1, lon1, lat2, lon2)
    return total_distance

def find_loop_routes(G, start_node, end_node, target_distance_m):
    """
    Creates large loop-based routes to match target distance when start/end points are close.
    Uses systematic geographical approach to find intermediate waypoints.
    """
    import random
    from math import cos, sin, radians
    
    # Calculate the direct shortest path and its distance
    shortest_path = nx.shortest_path(G, start_node, end_node, weight='length')
    shortest_distance = calculate_path_distance(G, shortest_path)
    
    # Check if this approach is necessary
    extra_distance_needed = target_distance_m - shortest_distance
    if extra_distance_needed < 1000:  # For small gaps, regular approach is better
        return []
    
    # Get start and end coordinates
    start_lat, start_lon = G.nodes[start_node]['y'], G.nodes[start_node]['x']
    end_lat, end_lon = G.nodes[end_node]['y'], G.nodes[end_node]['x']
    
    # Get all nodes in the graph
    all_nodes = list(G.nodes())
    
    # Distance from start to intermediate point should be roughly 1/3 to 1/2 of total
    target_mid_distance = target_distance_m / 3
    
    # Successful routes found
    loop_routes = []
    
    # 1. Try directional sampling approach - search in different directions from start
    directions = [
        (0, 1.0),    # North
        (45, 1.0),   # Northeast
        (90, 1.0),   # East
        (135, 1.0),  # Southeast
        (180, 1.0),  # South
        (225, 1.0),  # Southwest 
        (270, 1.0),  # West
        (315, 1.0),  # Northwest
    ]
    
    for angle, distance_factor in directions:
        # Skip directions after we've found enough routes
        if len(loop_routes) >= 10:
            break
            
        # Calculate a target point in this direction
        # distance_factor controls how far to go (as a fraction of target_mid_distance)
        target_distance = target_mid_distance * distance_factor
        
        # Convert angle to radians and calculate offset
        angle_rad = radians(angle)
        # Approximate conversion: 111,111 meters per degree of latitude
        # Longitude conversion varies with latitude (cos factor)
        lat_offset = (target_distance / 111111) * cos(angle_rad)
        lon_offset = (target_distance / (111111 * cos(radians(start_lat)))) * sin(angle_rad)
        
        # Target coordinates for intermediate point
        target_lat = start_lat + lat_offset
        target_lon = start_lon + lon_offset
        
        # Find closest nodes to this target point
        try:
            # Get nearest node to our target point
            nearest_node = ox.distance.nearest_nodes(G, target_lon, target_lat)
            
            # Try this node as potential intermediate point
            if nearest_node != start_node and nearest_node != end_node:
                try:
                    # Find paths through this intermediate point
                    path1 = nx.shortest_path(G, start_node, nearest_node, weight='length')
                    path2 = nx.shortest_path(G, nearest_node, end_node, weight='length')
                    
                    # Calculate distances
                    distance1 = calculate_path_distance(G, path1)
                    distance2 = calculate_path_distance(G, path2)
                    total_distance = distance1 + distance2
                    
                    # Calculate error percentage
                    error_percent = abs(total_distance - target_distance_m) / target_distance_m * 100
                    
                    # Only accept routes with <15% error
                    if error_percent <= 15:
                        # Combine the paths (excluding duplicate mid_node)
                        combined_path = path1 + path2[1:]
                        loop_routes.append((combined_path, total_distance))
                except nx.NetworkXNoPath:
                    continue
        except Exception:
            # Handle any exceptions with this direction and continue
            continue
    
    # 2. Try random sampling with distance-based filtering
    if len(loop_routes) < 10:
        # Try more random nodes with distance-based selection
        attempts = 0
        max_attempts = 50
        while attempts < max_attempts and len(loop_routes) < 15:
            attempts += 1
            
            # 30% of the time: use a targeted approach based on desired distance
            if random.random() < 0.3:
                # Try to find a node that's approximately 1/3 or 1/2 of the target distance away
                target_distance_factor = random.choice([1/3, 1/2, 2/3])
                target_distance_from_start = target_distance_m * target_distance_factor
                
                # Sort nodes by their proximity to the desired distance from start
                # This is expensive, so limit to a small random sample
                sample_size = min(100, len(all_nodes))
                sample_nodes = random.sample(all_nodes, sample_size)
                
                # Calculate distances from start to each node in sample
                distances_from_start = []
                for node in sample_nodes:
                    node_lat, node_lon = G.nodes[node]['y'], G.nodes[node]['x']
                    dist = haversine_distance(start_lat, start_lon, node_lat, node_lon)
                    distances_from_start.append((node, dist))
                
                # Sort by how close they are to our desired distance
                sorted_nodes = sorted(distances_from_start, 
                                      key=lambda x: abs(x[1] - target_distance_from_start))
                
                # Try the top 5 candidates
                for mid_node, _ in sorted_nodes[:5]:
                    if mid_node == start_node or mid_node == end_node:
                        continue
                        
                    try:
                        # Find paths through this intermediate point
                        path1 = nx.shortest_path(G, start_node, mid_node, weight='length')
                        path2 = nx.shortest_path(G, mid_node, end_node, weight='length')
                        
                        # Calculate distances
                        distance1 = calculate_path_distance(G, path1)
                        distance2 = calculate_path_distance(G, path2)
                        total_distance = distance1 + distance2
                        
                        # Calculate error percentage
                        error_percent = abs(total_distance - target_distance_m) / target_distance_m * 100
                        
                        # Only accept routes with <15% error
                        if error_percent <= 15:
                            # Combine the paths (excluding duplicate mid_node)
                            combined_path = path1 + path2[1:]
                            loop_routes.append((combined_path, total_distance))
                            break
                    except nx.NetworkXNoPath:
                        continue
            else:
                # Random sampling: choose random nodes and check if they create good routes
                mid_node = random.choice(all_nodes)
                if mid_node == start_node or mid_node == end_node:
                    continue
                    
                try:
                    # Find paths through this intermediate point
                    path1 = nx.shortest_path(G, start_node, mid_node, weight='length')
                    path2 = nx.shortest_path(G, mid_node, end_node, weight='length')
                    
                    # Calculate distances
                    distance1 = calculate_path_distance(G, path1)
                    distance2 = calculate_path_distance(G, path2)
                    total_distance = distance1 + distance2
                    
                    # Calculate error percentage
                    error_percent = abs(total_distance - target_distance_m) / target_distance_m * 100
                    
                    # Only accept routes with <15% error
                    if error_percent <= 15:
                        # Combine the paths (excluding duplicate mid_node)
                        combined_path = path1 + path2[1:]
                        loop_routes.append((combined_path, total_distance))
                except nx.NetworkXNoPath:
                    continue
    
    # 3. If still not enough, try multi-waypoint approach (for extremely large distances)
    if len(loop_routes) < 5 and extra_distance_needed > 8000:  # >5 miles extra
        # Try creating routes with two intermediate waypoints
        for _ in range(15):
            # Choose two random nodes
            if len(all_nodes) < 2:
                break
                
            try:
                mid_node1, mid_node2 = random.sample(all_nodes, 2)
                if mid_node1 == start_node or mid_node1 == end_node or mid_node2 == start_node or mid_node2 == end_node:
                    continue
                    
                # Find paths connecting all points
                path1 = nx.shortest_path(G, start_node, mid_node1, weight='length')
                path2 = nx.shortest_path(G, mid_node1, mid_node2, weight='length')
                path3 = nx.shortest_path(G, mid_node2, end_node, weight='length')
                
                # Calculate total distance
                distance1 = calculate_path_distance(G, path1)
                distance2 = calculate_path_distance(G, path2)
                distance3 = calculate_path_distance(G, path3)
                total_distance = distance1 + distance2 + distance3
                
                # Calculate error percentage
                error_percent = abs(total_distance - target_distance_m) / target_distance_m * 100
                
                # Only accept routes with <15% error
                if error_percent <= 15:
                    # Combine all paths
                    combined_path = path1 + path2[1:] + path3[1:]
                    loop_routes.append((combined_path, total_distance))
            except (nx.NetworkXNoPath, ValueError):
                continue
    
    # Sort by error percentage and return best routes
    return sorted(loop_routes, key=lambda r: abs(r[1] - target_distance_m))

def find_routes_near_target(G, start_node, end_node, target_distance_m, num_routes=5):
    """
    Find routes that match the target distance as precisely as possible.
    Uses an aggressive multi-strategy approach focused on distance accuracy.
    Returns a list of (path, distance) tuples sorted by closeness to target distance.
    """
    import random
    
    # Precompute the shortest path and its distance
    shortest_path = nx.shortest_path(G, start_node, end_node, weight='length')
    shortest_distance = calculate_path_distance(G, shortest_path)
    
    # If target is shorter than shortest path, just return the shortest
    if target_distance_m <= shortest_distance:
        return [(shortest_path, shortest_distance)]
    
    # Calculate how much extra distance we need
    extra_distance_needed = target_distance_m - shortest_distance
    
    # Define our maximum allowed error (15% of target distance)
    max_error = target_distance_m * 0.15
    
    # List to store candidate routes
    candidate_routes = [(shortest_path, shortest_distance)]
    exact_match_routes = []  # Routes within the error tolerance
    
    # Check if we have a very large gap that requires special handling
    extreme_gap = extra_distance_needed > 5000  # meters (about 3+ miles extra)
    very_large_gap = extra_distance_needed > 2000  # meters
    large_distance_gap = extra_distance_needed > 800  # meters
    
    if extreme_gap:
        print(f"Extreme gap detected: Need to add {extra_distance_needed/1609.34:.2f} miles to shortest path")
        
        # For extreme gaps, try a loop-based approach first
        loop_routes = find_loop_routes(G, start_node, end_node, target_distance_m)
        if loop_routes:
            exact_match_routes.extend(loop_routes)
            if len(exact_match_routes) >= num_routes:
                return sorted(exact_match_routes, key=lambda r: abs(r[1] - target_distance_m))[:num_routes]
    
    # Enhanced multi-strategy approach with more aggressive parameters for large gaps
    strategies = [
        # Strategy 1: Simple edge weight modification
        ("single_edge", 40, 500),  # (strategy, attempts, weight_multiplier)
        
        # Strategy 2: Multiple edge modifications
        ("multi_edge", 35, 2000),  # Modify multiple edges with higher weights
        
        # Strategy 3: Edge removal (extreme detours)
        ("edge_removal", 30, None),  # Complete edge removal for max detour
        
        # Strategy 4: Extreme multi-edge modification (more edges, higher weights)
        ("extreme_multi", 25, 5000),  # For very large distance gaps
        
        # Strategy 5: Ultra-aggressive modifications for extreme gaps
        ("ultra", 20, 10000)  # Maximum aggression for extreme gaps
    ]
    
    # Apply strategies in order, focusing on aggressive strategies for large distance gaps
    edges_tried = set()
    path_hashes = {str(shortest_path)}  # Track unique paths
    
    # Keep trying until we have enough routes within our error tolerance
    # or we've exhausted our strategies
    for strategy, max_attempts, weight_mul in strategies:
        # Skip less aggressive strategies based on the gap size
        if extreme_gap and strategy in ["single_edge", "multi_edge"]:
            continue
        if very_large_gap and strategy == "single_edge":
            continue
        if large_distance_gap and strategy == "single_edge" and len(exact_match_routes) < num_routes:
            continue
            
        # Increase attempts based on gap size
        actual_attempts = max_attempts
        if extreme_gap:
            actual_attempts *= 4  # Massively increase attempts for extreme gaps
        elif very_large_gap:
            actual_attempts *= 2
        elif len(exact_match_routes) < num_routes:
            actual_attempts = int(actual_attempts * 1.5)
        
        for _ in range(actual_attempts):
            # If we have enough exact matches, we can stop
            if len(exact_match_routes) >= num_routes * 2:
                break
                
            # Choose edges to modify based on strategy
            path_edges = list(zip(shortest_path[:-1], shortest_path[1:]))
            if not path_edges:
                break
                
            # Prefer edges near the middle of the path for better detours
            edge_weights = [1.0 - abs(2.0 * i / len(path_edges) - 1.0) for i in range(len(path_edges))]
            edge_weights_sum = sum(edge_weights)
            probabilities = [w / edge_weights_sum if edge_weights_sum > 0 else 1.0/len(path_edges) for w in edge_weights]
            
            # Get edges to modify based on strategy
            edges_to_modify = []
            if strategy == "single_edge":
                # Select a single edge
                edge_idx = random.choices(range(len(path_edges)), weights=probabilities, k=1)[0]
                edges_to_modify = [path_edges[edge_idx]]
            elif strategy == "multi_edge":
                # Select multiple edges (2-4) from different parts of the path
                num_edges = min(2 + int(extra_distance_needed / 500), 4)  # Scale with needed distance
                selected_indices = set()
                attempts = 0
                while len(selected_indices) < num_edges and len(selected_indices) < len(path_edges) and attempts < 15:
                    idx = random.choices(range(len(path_edges)), weights=probabilities, k=1)[0]
                    selected_indices.add(idx)
                    attempts += 1
                edges_to_modify = [path_edges[idx] for idx in selected_indices]
            elif strategy == "extreme_multi":
                # Select even more edges (3-8) for extreme detours
                num_edges = min(3 + int(extra_distance_needed / 400), 8)  # Increased max edges
                selected_indices = set()
                attempts = 0
                while len(selected_indices) < num_edges and len(selected_indices) < len(path_edges) and attempts < 20:
                    idx = random.choices(range(len(path_edges)), weights=probabilities, k=1)[0]
                    selected_indices.add(idx)
                    attempts += 1
                edges_to_modify = [path_edges[idx] for idx in selected_indices]
            elif strategy == "ultra":
                # Ultra-aggressive: modify almost all edges with very high weights
                # Select 50-80% of all edges for extreme cases
                edge_count = max(int(len(path_edges) * 0.5), min(int(len(path_edges) * 0.8), 12))
                selected_indices = set()
                # Prioritize edges more evenly throughout the path
                for _ in range(min(edge_count, len(path_edges))):
                    if not len(path_edges) - len(selected_indices):
                        break
                    remaining_indices = [i for i in range(len(path_edges)) if i not in selected_indices]
                    if remaining_indices:
                        idx = random.choice(remaining_indices)
                        selected_indices.add(idx)
                edges_to_modify = [path_edges[idx] for idx in selected_indices]
            elif strategy == "edge_removal":
                # Complete removal of an edge
                edge_idx = random.choices(range(len(path_edges)), weights=probabilities, k=1)[0]
                edges_to_modify = [path_edges[edge_idx]]
                # For extreme gaps, remove multiple edges
                if extreme_gap:
                    num_edges = min(3, len(path_edges) - 1)  # Don't remove all edges
                    for _ in range(num_edges - 1):
                        edge_idx = random.choices(range(len(path_edges)), weights=probabilities, k=1)[0]
                        if path_edges[edge_idx] not in edges_to_modify:
                            edges_to_modify.append(path_edges[edge_idx])
            
            # Skip if we've tried this exact combination before
            edge_combo = frozenset(edges_to_modify)
            if edge_combo in edges_tried:
                continue
            edges_tried.add(edge_combo)
            
            # Create a fresh modified graph for this attempt
            H = G.copy()
            
            # Store original weights to restore later
            original_weights = {}
            
            # Apply the modifications
            try:
                for edge in edges_to_modify:
                    if H.has_edge(edge[0], edge[1]):
                        # Store original weight
                        original_weights[edge] = H[edge[0]][edge[1]][0].get('length', 1)
                        
                        if strategy in ["single_edge", "multi_edge", "extreme_multi", "ultra"]:
                            # Modify weight - use higher multipliers for larger distance gaps
                            multiplier = weight_mul
                            if extra_distance_needed > 1500:  # Very large gaps need extreme multipliers
                                multiplier *= 3
                            if strategy == "extreme_multi" and very_large_gap:
                                multiplier *= 2  # Double again for extreme cases
                            if extreme_gap:
                                multiplier *= 5  # 5x higher for extreme gaps
                            if strategy == "ultra":
                                multiplier *= random.randint(2, 10)  # Add randomness for ultra strategy
                            
                            H[edge[0]][edge[1]][0]['length'] = original_weights[edge] * multiplier
                        elif strategy == "edge_removal":
                            # Remove edge (effectively infinite weight)
                            H.remove_edge(edge[0], edge[1])
                
                # Find a new path with the modified graph
                try:
                    detour_path = nx.shortest_path(H, start_node, end_node, weight='length')
                    detour_distance = calculate_path_distance(G, detour_path)
                    path_hash = str(detour_path)
                    
                    # Check if this route is unique
                    if path_hash not in path_hashes:
                        path_hashes.add(path_hash)
                        
                        # Check how close it is to our target distance
                        distance_error = abs(detour_distance - target_distance_m)
                        
                        # For extreme gaps, we'll accept routes that are at least 70% of target
                        min_acceptable = shortest_distance
                        if extreme_gap:
                            min_acceptable = max(shortest_distance, target_distance_m * 0.7)
                        
                        # Only keep routes that are reasonably close to target
                        if (detour_distance <= target_distance_m * 2.0 and  # Allow up to 2x target
                            detour_distance >= min_acceptable):  # Must be longer than shortest
                            
                            candidate_routes.append((detour_path, detour_distance))
                            
                            # If this route is within our error tolerance, add it to exact matches
                            if distance_error <= max_error:
                                exact_match_routes.append((detour_path, detour_distance))
                                
                except nx.NetworkXNoPath:
                    pass  # No alternative path exists with these modifications
            except Exception as e:
                # Handle any unexpected errors in graph modification
                pass
            finally:
                # Restore the original graph weights if needed
                if strategy != "edge_removal":
                    for edge, weight in original_weights.items():
                        if H.has_edge(edge[0], edge[1]):
                            H[edge[0]][edge[1]][0]['length'] = weight
    
    # If we found routes within error tolerance, use those
    if exact_match_routes:
        # Sort by how close they are to the target distance
        sorted_exact = sorted(exact_match_routes, key=lambda r: abs(r[1] - target_distance_m))
        
        # Return the top routes, ensuring no duplicates
        unique_routes = []
        seen_paths = set()
        for path, distance in sorted_exact:
            path_str = str(path)
            if path_str not in seen_paths:
                seen_paths.add(path_str)
                unique_routes.append((path, distance))
            if len(unique_routes) >= num_routes:
                break
        
        return unique_routes
    else:
        # Fall back to the closest routes we could find
        sorted_routes = sorted(candidate_routes, key=lambda r: abs(r[1] - target_distance_m))
        
        # Return the top routes, ensuring no duplicates
        unique_routes = []
        seen_paths = set()
        for path, distance in sorted_routes:
            path_str = str(path)
            if path_str not in seen_paths:
                seen_paths.add(path_str)
                unique_routes.append((path, distance))
            if len(unique_routes) >= num_routes:
                break
        
        return unique_routes

def analyze_route_directions(G, routes):
    """Analyze the directional distribution of generated routes"""
    directions = {'north': 0, 'south': 0, 'east': 0, 'west': 0}
    
    for path, distance in routes:
        if len(path) < 2:
            continue
            
        # Get start and end points
        start_lat = G.nodes[path[0]]['y']
        start_lon = G.nodes[path[0]]['x']
        
        # Find the furthest point from start
        max_distance = 0
        furthest_point = None
        
        for node in path[1:]:
            node_lat = G.nodes[node]['y']
            node_lon = G.nodes[node]['x']
            dist = haversine_distance(start_lat, start_lon, node_lat, node_lon)
            if dist > max_distance:
                max_distance = dist
                furthest_point = (node_lat, node_lon)
        
        if furthest_point:
            # Determine primary direction
            lat_diff = furthest_point[0] - start_lat
            lon_diff = furthest_point[1] - start_lon
            
            if abs(lat_diff) > abs(lon_diff):
                directions['north' if lat_diff > 0 else 'south'] += 1
            else:
                directions['east' if lon_diff > 0 else 'west'] += 1
    
    return directions

def find_perfect_loop_routes(G, start_node, target_distance_m, num_routes=5, max_error_percent=15.0):
    """
    Find loop routes that start and end at the same point with distance close to target.
    Uses multiple strategies to find diverse routes.
    Returns a list of (path, distance) tuples sorted by closeness to target distance.
    """
    import networkx as nx
    
    # Strategic waypoint-based loop route generation
    import random
    
    # Helper: Get graph bounds and calculate safe radius
    def get_graph_bounds(G):
        """Get the geographical bounds of the graph"""
        lats = [G.nodes[node]['y'] for node in G.nodes()]
        lons = [G.nodes[node]['x'] for node in G.nodes()]
        return {
            'min_lat': min(lats), 'max_lat': max(lats),
            'min_lon': min(lons), 'max_lon': max(lons),
            'center_lat': (min(lats) + max(lats)) / 2,
            'center_lon': (min(lons) + max(lons)) / 2
        }

    def calculate_max_safe_radius(G, start_lat, start_lon):
        """Calculate maximum radius that stays within graph bounds"""
        bounds = get_graph_bounds(G)
        
        # Calculate distances to each boundary
        distances = [
            haversine_distance(start_lat, start_lon, bounds['max_lat'], start_lon),
            haversine_distance(start_lat, start_lon, bounds['min_lat'], start_lon),
            haversine_distance(start_lat, start_lon, start_lat, bounds['max_lon']),
            haversine_distance(start_lat, start_lon, start_lat, bounds['min_lon'])
        ]
        
        # Use 80% of minimum distance to stay safely within bounds
        return min(distances) * 0.8
    
    # Helper: Calculate lat/lon at a given distance and bearing from a point
    def calculate_point_at_distance(lat, lon, distance_m, angle_deg):
        """
        Calculate lat/lon at a given distance and bearing from a point.
        angle_deg: 0 = North, 90 = East, 180 = South, 270 = West (compass bearing)
        """
        R = 6371000  # Earth radius in meters
        d = distance_m / R  # Angular distance in radians
        
        # Convert compass bearing to radians
        bearing_rad = math.radians(angle_deg)
        
        lat_rad = math.radians(lat)
        lon_rad = math.radians(lon)
        
        # Use proper spherical geometry formulas with correct bearing convention
        new_lat_rad = math.asin(
            math.sin(lat_rad) * math.cos(d) +
            math.cos(lat_rad) * math.sin(d) * math.cos(bearing_rad)
        )
        
        new_lon_rad = lon_rad + math.atan2(
            math.sin(bearing_rad) * math.sin(d) * math.cos(lat_rad),
            math.cos(d) - math.sin(lat_rad) * math.sin(new_lat_rad)
        )
        
        return math.degrees(new_lat_rad), math.degrees(new_lon_rad)

    # Helper: Generate random orientation and balanced angles
    def generate_random_orientation():
        """Generate a completely random starting orientation (0-360 degrees)"""
        return random.uniform(0, 360)

    def generate_balanced_angles(num_points, base_orientation=None):
        """Generate evenly spaced angles with random starting orientation"""
        if base_orientation is None:
            base_orientation = generate_random_orientation()
        
        angles = []
        angle_step = 360 / num_points
        
        for i in range(num_points):
            # Base angle with random orientation
            angle = (base_orientation + i * angle_step) % 360
            # Add small random variation (±15 degrees) for natural variation
            angle += random.uniform(-15, 15)
            angles.append(angle % 360)
        
        return angles

    # Helper: Build route through waypoints and back to start
    def build_multi_waypoint_route(G, start_node, waypoints):
        path_segments = []
        current = start_node
        for waypoint in waypoints:
            try:
                segment = nx.shortest_path(G, current, waypoint, weight='length')
                if path_segments:
                    segment = segment[1:]
                path_segments.extend(segment)
                current = waypoint
            except nx.NetworkXNoPath:
                return None
        # Return to start
        try:
            final_segment = nx.shortest_path(G, current, start_node, weight='length')[1:]
            path_segments.extend(final_segment)
        except nx.NetworkXNoPath:
            return None
        return path_segments

    # Helper: Generate triangle waypoints
    def generate_triangle_waypoints(G, start_lat, start_lon, radius):
        waypoints = []
        angles = generate_balanced_angles(3)  # Completely random orientation
        
        for angle in angles:
            # Random radius variation
            varied_radius = radius * random.uniform(0.6, 0.9)
            waypoint_lat, waypoint_lon = calculate_point_at_distance(start_lat, start_lon, varied_radius, angle)
            nearest_node = ox.distance.nearest_nodes(G, waypoint_lon, waypoint_lat)
            waypoints.append(nearest_node)
        return waypoints

    # Helper: Generate rectangle waypoints
    def generate_rectangle_waypoints(G, start_lat, start_lon, radius):
        waypoints = []
        angles = generate_balanced_angles(4)  # Completely random orientation
        
        for angle in angles:
            varied_radius = radius * random.uniform(0.5, 0.8)
            waypoint_lat, waypoint_lon = calculate_point_at_distance(start_lat, start_lon, varied_radius, angle)
            nearest_node = ox.distance.nearest_nodes(G, waypoint_lon, waypoint_lat)
            waypoints.append(nearest_node)
        return waypoints

    # Helper: Generate star waypoints (5 points)
    def generate_star_waypoints(G, start_lat, start_lon, radius):
        waypoints = []
        angles = generate_balanced_angles(5)  # Completely random orientation
        
        for angle in angles:
            varied_radius = radius * random.uniform(0.4, 0.7)
            waypoint_lat, waypoint_lon = calculate_point_at_distance(start_lat, start_lon, varied_radius, angle)
            nearest_node = ox.distance.nearest_nodes(G, waypoint_lon, waypoint_lat)
            waypoints.append(nearest_node)
        return waypoints

    # Helper: Generate figure-8 waypoints (2 loops)
    def generate_figure8_waypoints(G, start_lat, start_lon, radius):
        waypoints = []
        # Generate 4 points for figure-8 pattern with random orientation
        base_orientation = generate_random_orientation()
        base_angles = [60, 240, 120, 300]  # Figure-8 specific angles
        
        for base_angle in base_angles:
            angle = (base_orientation + base_angle + random.uniform(-10, 10)) % 360
            varied_radius = radius * random.uniform(0.5, 0.7)
            waypoint_lat, waypoint_lon = calculate_point_at_distance(start_lat, start_lon, varied_radius, angle)
            nearest_node = ox.distance.nearest_nodes(G, waypoint_lon, waypoint_lat)
            waypoints.append(nearest_node)
        return waypoints

    # Helper: Generate pentagon waypoints (5 points)
    def generate_pentagon_waypoints(G, start_lat, start_lon, radius):
        waypoints = []
        angles = generate_balanced_angles(5)  # Completely random orientation
        
        for angle in angles:
            varied_radius = radius * random.uniform(0.5, 0.7)
            waypoint_lat, waypoint_lon = calculate_point_at_distance(start_lat, start_lon, varied_radius, angle)
            nearest_node = ox.distance.nearest_nodes(G, waypoint_lon, waypoint_lat)
            waypoints.append(nearest_node)
        return waypoints

    # Helper: Generate hexagon waypoints (6 points)
    def generate_hexagon_waypoints(G, start_lat, start_lon, radius):
        waypoints = []
        angles = generate_balanced_angles(6)  # Completely random orientation
        
        for angle in angles:
            varied_radius = radius * random.uniform(0.4, 0.6)
            waypoint_lat, waypoint_lon = calculate_point_at_distance(start_lat, start_lon, varied_radius, angle)
            nearest_node = ox.distance.nearest_nodes(G, waypoint_lon, waypoint_lat)
            waypoints.append(nearest_node)
        return waypoints

    # Helper: Generate octagon waypoints (8 points)
    def generate_octagon_waypoints(G, start_lat, start_lon, radius):
        waypoints = []
        angles = generate_balanced_angles(8)  # Completely random orientation
        
        for angle in angles:
            varied_radius = radius * random.uniform(0.3, 0.5)  # Smaller radius for more waypoints
            waypoint_lat, waypoint_lon = calculate_point_at_distance(start_lat, start_lon, varied_radius, angle)
            nearest_node = ox.distance.nearest_nodes(G, waypoint_lon, waypoint_lat)
            waypoints.append(nearest_node)
        return waypoints

    # Helper: Generate random polygon waypoints
    def generate_random_polygon_waypoints(G, start_lat, start_lon, radius):
        """Generate completely random polygon with 3-5 waypoints"""
        waypoints = []
        num_points = random.randint(3, 5)
        # Generate completely random angles with better distribution
        angles = [random.uniform(0, 360) for _ in range(num_points)]
        angles.sort()  # Sort for proper polygon
        
        for angle in angles:
            varied_radius = radius * random.uniform(0.4, 0.8)
            waypoint_lat, waypoint_lon = calculate_point_at_distance(start_lat, start_lon, varied_radius, angle)
            nearest_node = ox.distance.nearest_nodes(G, waypoint_lon, waypoint_lat)
            waypoints.append(nearest_node)
        return waypoints

    # Main logic
    candidate_routes = []
    path_hashes = set()
    start_lat, start_lon = G.nodes[start_node]['y'], G.nodes[start_node]['x']
    
    # CRITICAL FIX: Reduce waypoint radius significantly
    # The current 0.4 multiplier creates routes that are too long
    waypoint_radius = target_distance_m * 0.15  # Changed from 0.4 to 0.15

    # Try multiple radius sizes for better accuracy
    radius_variations = [
        target_distance_m * 0.12,  # Small loops
        target_distance_m * 0.15,  # Medium loops  
        target_distance_m * 0.18,  # Larger loops
        target_distance_m * 0.22   # Even larger for variety
    ]

    # Try geometric patterns with multiple radius sizes
    patterns = []

    # Generate patterns with different radius sizes and multiple variations
    for radius in radius_variations:
        # Generate multiple variations of each pattern type with different orientations
        for variation in range(2):  # 2 variations per radius per pattern
            patterns.append(generate_triangle_waypoints(G, start_lat, start_lon, radius))
            patterns.append(generate_rectangle_waypoints(G, start_lat, start_lon, radius))
            patterns.append(generate_star_waypoints(G, start_lat, start_lon, radius))
            patterns.append(generate_pentagon_waypoints(G, start_lat, start_lon, radius))
            patterns.append(generate_hexagon_waypoints(G, start_lat, start_lon, radius))
            patterns.append(generate_octagon_waypoints(G, start_lat, start_lon, radius))
            patterns.append(generate_figure8_waypoints(G, start_lat, start_lon, radius))
        
        # Add extra random patterns for each radius
        for _ in range(3):
            patterns.append(generate_random_polygon_waypoints(G, start_lat, start_lon, radius))

    # Shuffle the order of patterns multiple times for maximum randomness
    for _ in range(3):
        random.shuffle(patterns)
    distances = []
    
    # Process patterns and filter by error tolerance early
    for waypoints in patterns:
        if len(candidate_routes) >= num_routes * 3:  # Generate more candidates
            break
        path = build_multi_waypoint_route(G, start_node, waypoints)
        if path:
            distance = calculate_path_distance(G, path)
            path_hash = str(path)
            distances.append(distance)
            
            # Only add routes that are within 1200 meters of target distance
            if ((distance > target_distance_m - 1200) and (distance < target_distance_m + 1200)) and path_hash not in path_hashes:
                path_hashes.add(path_hash)
                candidate_routes.append((path, distance))

    # Get and print the average distance and error percentage
    if distances:
        avg_distance = sum(distances) / len(distances)
        avg_error = sum(abs(d - target_distance_m) / target_distance_m * 100 for d in distances) / len(distances)
        print(f"Target: {target_distance_m}m, Average Distance: {avg_distance:.0f}m, Average Error: {avg_error:.1f}%")

    # Analyze directional distribution of generated routes
    if candidate_routes:
        direction_analysis = analyze_route_directions(G, candidate_routes)
        print(f"Directional distribution: {direction_analysis}")
        
        # Calculate balance score (closer to 25% each = better balance)
        total_routes = sum(direction_analysis.values())
        if total_routes > 0:
            balance_scores = [abs(count/total_routes - 0.25) for count in direction_analysis.values()]
            avg_balance_score = sum(balance_scores) / 4
            print(f"Balance score (lower = better): {avg_balance_score:.3f}")

    # Sort and return best routes
    sorted_routes = sorted(candidate_routes, key=lambda r: abs(r[1] - target_distance_m))
    return sorted_routes[:num_routes] if len(sorted_routes) >= num_routes else sorted_routes

def calculate_mile_markers(G, path, target_distance_miles):
    """
    Calculate mile marker positions along a route path.
    Returns a list of coordinates where each mile marker should be placed.
    """
    if not path or len(path) < 2:
        return []
    
    mile_markers = []
    mile_distance_m = 1609.34  # 1 mile in meters
    current_distance = 0
    next_mile_target = mile_distance_m
    
    # Don't add markers if route is less than 0.5 miles
    if target_distance_miles < 0.5:
        return []
    
    for i in range(len(path) - 1):
        node1, node2 = path[i], path[i + 1]
        lat1, lon1 = G.nodes[node1]['y'], G.nodes[node1]['x']
        lat2, lon2 = G.nodes[node2]['y'], G.nodes[node2]['x']
        
        segment_distance = haversine_distance(lat1, lon1, lat2, lon2)
        
        # Check if we cross a mile marker in this segment
        while current_distance + segment_distance >= next_mile_target:
            # Calculate how far along this segment the mile marker should be
            remaining_to_mile = next_mile_target - current_distance
            fraction = remaining_to_mile / segment_distance if segment_distance > 0 else 0
            
            # Interpolate the position along the segment
            marker_lat = lat1 + (lat2 - lat1) * fraction
            marker_lon = lon1 + (lon2 - lon1) * fraction
            
            mile_number = len(mile_markers) + 1
            mile_markers.append({
                "mile": mile_number,
                "coordinates": [marker_lon, marker_lat],  # [lon, lat] for GeoJSON
                "distance_meters": next_mile_target,
                "distance_miles": next_mile_target / 1609.34
            })
            
            next_mile_target += mile_distance_m
            
            # Stop if we've reached the target number of miles
            if mile_number >= int(target_distance_miles):
                break
        
        current_distance += segment_distance
        
        # Stop if we've placed enough markers
        if len(mile_markers) >= int(target_distance_miles):
            break
    
    return mile_markers

def create_route_geojson(G, path):
    """
    Convert a path of nodes into GeoJSON format for frontend display.
    """
    route_coords = [(G.nodes[n]['x'], G.nodes[n]['y']) for n in path]
    return {
        "type": "Feature",
        "geometry": {
            "type": "LineString",
            "coordinates": route_coords,
        },
        "properties": {},
    }

@app.get("/routes/")
def get_routes(
    start_lat: float = Query(...),
    start_lon: float = Query(...),
    end_lat: float = Query(...),
    end_lon: float = Query(...),
    distance_miles: float = Query(..., description="Desired route distance in miles"),
    dist: int = Query(PRELOADED_DIST, description="Graph preload radius in meters"),
    max_error_percent: float = Query(15.0, description="Maximum allowed error percentage from target distance"),
    include_elevation: bool = Query(True, description="Whether to include elevation data (may slow down response)")
):
    """
    Find walking routes between two points that match the desired distance as closely as possible.
    Returns the 5 routes that most closely match the target distance.
    
    Process:
    1. Check route cache first
    2. Get or create an OSM graph for the area
    3. Find the nearest road nodes to start/end points
    4. Search for multiple paths that match the target distance precisely (within 15% error)
    5. Cache and return the routes as GeoJSON with error percentages
    """
    # Try to get route from cache first
    cached_route = route_cache.load_route(start_lat, start_lon, end_lat, end_lon, distance_miles)
    if cached_route:
        return cached_route
    
    try:
        # Step 1: Get the road network graph for this area
        # For large distance requests, get a larger graph
        effective_dist = dist
        if distance_miles > 3:
            effective_dist = max(dist, min(1500, int(distance_miles * 400)))  # Scale with distance
            
        G = get_or_create_graph(start_lat, start_lon, end_lat, end_lon, effective_dist)
        
        # Step 2: Find the nearest road nodes to our start/end points
        start_node = ox.distance.nearest_nodes(G, start_lon, start_lat)
        end_node = ox.distance.nearest_nodes(G, end_lon, end_lat)
        
        # Step 3: Convert target distance from miles to meters
        target_distance_m = distance_miles * 1609.34
        
        # Step 4: First try with the enhanced loop finding approach for large distances
        routes = []
        
        # Calculate shortest path to check gap size
        shortest_path = nx.shortest_path(G, start_node, end_node, weight='length')
        shortest_distance = calculate_path_distance(G, shortest_path)
        extra_distance_needed = target_distance_m - shortest_distance
        
        # If we need to add significant distance, prioritize loop-based routes
        if extra_distance_needed > 1000:  # Over 1km / 0.6mi extra
            loop_routes = find_loop_routes(G, start_node, end_node, target_distance_m)
            routes.extend(loop_routes)
        
        # If we still need more routes, use the general approach
        if len(routes) < 5:
            general_routes = find_routes_near_target(G, start_node, end_node, target_distance_m, num_routes=10)
            # Filter routes to only include those with <15% error
            filtered_routes = []
            for path, distance in general_routes:
                error_percent = abs(distance - target_distance_m) / target_distance_m * 100
                if error_percent <= max_error_percent:
                    filtered_routes.append((path, distance))
            routes.extend(filtered_routes)
        
        # Remove any duplicate routes
        unique_routes = []
        seen_paths = set()
        for path, distance in routes:
            path_hash = str(path)
            if path_hash not in seen_paths:
                seen_paths.add(path_hash)
                unique_routes.append((path, distance))
        
        # Sort by how close they are to the target distance
        sorted_routes = sorted(unique_routes, key=lambda r: abs(r[1] - target_distance_m))
        
        # Only take routes with error <= 15%
        final_routes = []
        for path, distance in sorted_routes:
            error_percent = abs(distance - target_distance_m) / target_distance_m * 100
            if error_percent <= max_error_percent:
                final_routes.append((path, distance))
                if len(final_routes) >= 5:
                    break
        
        # Step 5: Convert routes to GeoJSON with error tracking and mile markers
        routes_geojson = []
        for i, (path, distance) in enumerate(final_routes):
            route_geojson = create_route_geojson(G, path)
            error_percent = abs(distance - target_distance_m) / target_distance_m * 100
            
            # Calculate mile markers for this route
            mile_markers = calculate_mile_markers(G, path, distance_miles)
            
            # Calculate elevation profile if requested
            elevation_data = None
            if include_elevation:
                elevation_data = get_route_elevation_profile(G, path)
            
            route_info = {
                "id": f"route_{i+1}",
                "geojson": route_geojson,
                "distance_meters": distance,
                "distance_miles": distance / 1609.34,
                "error_percent": round(error_percent, 2),
                "mile_markers": mile_markers
            }
            
            # Add elevation data if requested
            if include_elevation and elevation_data:
                route_info.update({
                    "elevation_gain": elevation_data["elevation_gain"],
                    "elevation_loss": elevation_data["elevation_loss"],
                    "max_elevation": elevation_data["max_elevation"],
                    "min_elevation": elevation_data["min_elevation"],
                    "elevation_profile": elevation_data["elevation_profile"],
                    "smoothed_elevation_profile": elevation_data["smoothed_elevation_profile"]
                })
            else:
                route_info["elevation_gain"] = None
            
            routes_geojson.append(route_info)
        
        # Step 6: Prepare the response with target distance info
        result = {
            "snapped_start": [G.nodes[start_node]['y'], G.nodes[start_node]['x']],
            "snapped_end": [G.nodes[end_node]['y'], G.nodes[end_node]['x']],
            "target_distance_meters": target_distance_m,
            "target_distance_miles": distance_miles,
            "routes": routes_geojson
        }
        
        # Cache the result for future requests
        route_cache.save_route(result, start_lat, start_lon, end_lat, end_lon, distance_miles)
        
        return result
        
    except nx.NetworkXNoPath:
        return {"error": "No path found between points."}

@app.get("/loop-routes/")
def get_loop_routes(
    start_lat: float = Query(...),
    start_lon: float = Query(...),
    distance_miles: float = Query(..., description="Desired route distance in miles"),
    max_error_percent: float = Query(500.0, description="Maximum allowed error percentage from target distance"),
    include_elevation: bool = Query(True, description="Whether to include elevation data (may slow down response)")
):
    """
    Find loop routes that start and end at the same point matching the desired distance.
    Returns up to 5 routes that most closely match the target distance.
    
    Process:
    1. Get or create an OSM graph for the area
    2. Find the nearest road node to start point
    3. Convert target distance from miles to meters
    4. Search for multiple loop paths that match the target distance precisely (1200 meters)
    5. Cache and return the routes as GeoJSON with error percentages
    """
    
    try:
        # Step 1: Get the road network graph for this area
        # For loop routes, we need a larger graph since we're going out and back
        effective_dist = min(7000, int(distance_miles * 1000) * 0.5)  # Scale with distance
            
        G = get_or_create_graph(start_lat, start_lon, start_lat, start_lon, effective_dist)
        
        # Step 2: Find the nearest road node to our start point
        start_node = ox.distance.nearest_nodes(G, start_lon, start_lat)
        
        # Step 3: Convert target distance from miles to meters
        target_distance_m = distance_miles * 1609.34
        
        # Step 4: Find loop routes
        routes = find_perfect_loop_routes(G, start_node, target_distance_m, num_routes=5, max_error_percent=max_error_percent)
        
        # Step 5: Convert routes to GeoJSON with error tracking and mile markers
        routes_geojson = []
        for i, (path, distance) in enumerate(routes):
            route_geojson = create_route_geojson(G, path)
            error_percent = abs(distance - target_distance_m) / target_distance_m * 100
            
            # Calculate mile markers for this route
            mile_markers = calculate_mile_markers(G, path, distance_miles)
            
            # Calculate elevation profile if requested
            elevation_data = None
            if include_elevation:
                elevation_data = get_route_elevation_profile(G, path)
            
            route_info = {
                "id": f"loop_{i+1}",
                "geojson": route_geojson,
                "distance_meters": distance,
                "distance_miles": distance / 1609.34,
                "error_percent": round(error_percent, 2),
                "mile_markers": mile_markers
            }
            
            # Add elevation data if requested
            if include_elevation and elevation_data:
                route_info.update({
                    "elevation_gain": elevation_data["elevation_gain"],
                    "elevation_loss": elevation_data["elevation_loss"],
                    "max_elevation": elevation_data["max_elevation"],
                    "min_elevation": elevation_data["min_elevation"],
                    "elevation_profile": elevation_data["elevation_profile"],
                    "smoothed_elevation_profile": elevation_data["smoothed_elevation_profile"]
                })
            else:
                route_info["elevation_gain"] = None
            
            routes_geojson.append(route_info)
        
        # Step 6: Prepare the response with target distance info
        result = {
            "snapped_start": [G.nodes[start_node]['y'], G.nodes[start_node]['x']],
            "snapped_end": [G.nodes[start_node]['y'], G.nodes[start_node]['x']],  # Same as start for loops
            "target_distance_meters": target_distance_m,
            "target_distance_miles": distance_miles,
            "routes": routes_geojson
        }
        
        # Cache the result for future requests (using same coordinates for start and end)
        # route_cache.save_route(result, start_lat, start_lon, start_lat, start_lon, distance_miles)
        
        return result
        
    except Exception as e:
        return {"error": f"Failed to generate loop routes: {str(e)}"}
