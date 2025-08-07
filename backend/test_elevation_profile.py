import sys
from pathlib import Path
import networkx as nx

# Add backend directory to sys.path
sys.path.append(str(Path(__file__).parent))
import elevation_utils


def test_get_route_elevation_profile_handles_zero_elevation(monkeypatch):
    G = nx.Graph()
    G.add_node(1, x=0.0, y=0.0)
    G.add_node(2, x=1.0, y=1.0)

    def fake_get_elevation_data(coords):
        return [0.0, 0.0]

    monkeypatch.setattr(elevation_utils, "get_elevation_data", fake_get_elevation_data)

    profile = elevation_utils.get_route_elevation_profile(G, [1, 2], sample_rate=1)

    assert profile["max_elevation"] == 0.0
    assert profile["min_elevation"] == 0.0
