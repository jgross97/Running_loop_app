#!/usr/bin/env python3
"""
Simple test script to verify elevation functionality works correctly.
"""

import sys
import requests
from elevation_utils import get_elevation_data, get_route_elevation_profile, smooth_elevations

def test_elevation_api():
    """Test the basic elevation API functionality."""
    print("Testing elevation API...")
    
    # Test coordinates around Philadelphia area
    coords = [
        (40.0781, -75.2961),
        (40.0785, -75.2965), 
        (40.0790, -75.2970),
        (40.0795, -75.2975)
    ]
    
    try:
        elevations = get_elevation_data(coords)
        print(f"Raw elevations: {elevations}")
        
        # Test smoothing
        valid_elevations = [e for e in elevations if e is not None]
        if len(valid_elevations) >= 2:
            smoothed = smooth_elevations(valid_elevations)
            print(f"Smoothed elevations: {smoothed}")
        
        return True
    except Exception as e:
        print(f"Elevation API test failed: {e}")
        return False

def test_routes_endpoint():
    """Test the routes endpoint with elevation enabled."""
    print("\nTesting routes endpoint with elevation...")
    
    # Test the actual API endpoint
    url = "http://localhost:8000/routes/"
    params = {
        "start_lat": 40.0781,
        "start_lon": -75.2961,
        "end_lat": 40.0785,
        "end_lon": -75.2965,
        "distance_miles": 1.0,
        "include_elevation": True
    }
    
    try:
        response = requests.get(url, params=params, timeout=30)
        if response.status_code == 200:
            data = response.json()
            print("Routes endpoint test successful!")
            
            # Check if elevation data is present
            if data.get("routes"):
                first_route = data["routes"][0]
                has_elevation = first_route.get("elevation_gain") is not None
                has_profile = "elevation_profile" in first_route
                has_smoothed = "smoothed_elevation_profile" in first_route
                
                print(f"Has elevation gain: {has_elevation}")
                print(f"Has elevation profile: {has_profile}")  
                print(f"Has smoothed elevation profile: {has_smoothed}")
                
                if has_elevation:
                    print(f"Elevation gain: {first_route.get('elevation_gain')} meters")
                    print(f"Elevation loss: {first_route.get('elevation_loss')} meters")
                    print(f"Max elevation: {first_route.get('max_elevation')} meters")
                    print(f"Min elevation: {first_route.get('min_elevation')} meters")
            
            return True
        else:
            print(f"Routes endpoint returned status {response.status_code}")
            print(f"Response: {response.text}")
            return False
    except requests.exceptions.ConnectionError:
        print("Could not connect to server. Make sure the API is running on localhost:8000")
        return False
    except Exception as e:
        print(f"Routes endpoint test failed: {e}")
        return False

if __name__ == "__main__":
    print("Running elevation functionality tests...\n")
    
    # Test 1: Basic elevation API
    api_success = test_elevation_api()
    
    # Test 2: Routes endpoint (only if API test passed)
    if api_success:
        endpoint_success = test_routes_endpoint()
    else:
        endpoint_success = False
        print("Skipping endpoint test due to API failure")
    
    print(f"\n=== Test Results ===")
    print(f"Elevation API: {'PASS' if api_success else 'FAIL'}")
    print(f"Routes Endpoint: {'PASS' if endpoint_success else 'FAIL'}")
    
    if api_success and endpoint_success:
        print("All tests passed! 🎉")
        sys.exit(0)
    else:
        print("Some tests failed. Check the output above.")
        sys.exit(1)
