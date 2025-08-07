import networkx as nx
import osmnx as ox
from typing import Optional

def simplify_graph(G: nx.Graph, tolerance: float = 0.0001) -> nx.Graph:
    """
    Simplify graph to reduce complexity while maintaining connectivity.
    This speeds up routing calculations significantly.
    
    Args:
        G: The input graph
        tolerance: Tolerance for simplification (smaller = more detailed)
    
    Returns:
        Simplified graph
    """
    try:
        # Make a copy to avoid modifying the original
        G_simple = G.copy()
        
        # Simplify graph topology - removes nodes with only 2 connections
        G_simple = ox.simplification.simplify_graph(G_simple)
        
        # Get the largest connected component to ensure connectivity
        if not nx.is_connected(G_simple.to_undirected()):
            largest_cc = max(nx.connected_components(G_simple.to_undirected()), key=len)
            G_simple = G_simple.subgraph(largest_cc).copy()
        
        print(f"Graph simplified: {len(G.nodes)} -> {len(G_simple.nodes)} nodes")
        return G_simple
        
    except Exception as e:
        print(f"Graph simplification failed: {e}, returning original graph")
        return G

def preprocess_graph(G: nx.Graph) -> nx.Graph:
    """
    Apply all preprocessing steps to optimize the graph for routing.
    
    Args:
        G: Raw OSM graph
        
    Returns:
        Preprocessed graph ready for fast routing
    """
    # First simplify the graph
    G_processed = simplify_graph(G)
    
    # Add any additional preprocessing here in the future
    # For example: edge weight preprocessing, elevation data, etc.
    
    return G_processed
