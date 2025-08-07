import React from 'react';
import { MapContainer, TileLayer, GeoJSON, Marker, Popup, Circle, useMapEvent, useMap, CircleMarker } from 'react-leaflet';
import L from 'leaflet';
import 'leaflet-polylinedecorator';
import 'leaflet/dist/leaflet.css';
import '../styles/MapView.css';

interface MileMarker {
  mile: number;
  coordinates: [number, number]; // [lon, lat]
  distance_meters: number;
  distance_miles: number;
}

interface Route {
  id: string;
  geojson: any;
  mile_markers?: MileMarker[];
  elevation_profile?: number[];
  smoothed_elevation_profile?: number[];
  max_elevation?: number;
  min_elevation?: number;
}

interface MapViewProps {
  routes: Route[];
  selectedRouteId: string | null;
  startPoint?: [number, number] | null;
  endPoint?: [number, number] | null;
  snappedStart: [number, number] | null;
  snappedEnd?: [number, number] | null;
  onMapClick?: (lat: number, lon: number) => void;
  zoom: number;
  setZoom: (z: number) => void;
  selectedMiles?: number; // Add this prop for selected distance in miles
  loading?: boolean; // Add loading prop for loading indicator
  routesLoaded?: boolean; // Add this to track when useRoutes completes
}

const MapClickHandler: React.FC<{ onMapClick?: (lat: number, lon: number) => void }> = ({ onMapClick }) => {
  useMapEvent('click', (e) => {
    if (onMapClick) {
      onMapClick(e.latlng.lat, e.latlng.lng);
    }
  });
  return null;
};

const ZoomListener: React.FC<{ setZoom: (z: number) => void }> = ({ setZoom }) => {
  useMapEvent('zoomend', (e) => {
    setZoom(e.target.getZoom());
  });
  return null;
};

// Add component to handle map recentering and zoom adjustment
const MapRecenterHandler: React.FC<{ 
  startPoint: [number, number] | null; 
  selectedMiles: number;
  routesLoaded: boolean;
  setZoom: (z: number) => void;
}> = ({ startPoint, selectedMiles, routesLoaded, setZoom }) => {
  const map = useMap();
  const prevRoutesLoaded = React.useRef(false);

  React.useEffect(() => {
    // Only trigger when routesLoaded changes from false to true
    if (routesLoaded && !prevRoutesLoaded.current && startPoint && selectedMiles > 0) {
      // Calculate radius in meters
      const radiusMeters = (selectedMiles * 500) * 0.5;
      
      // Calculate zoom level to fit the circle vertically
      // Leaflet's formula: meters per pixel = 40075016.686 * Math.cos(lat * Math.PI/180) / Math.pow(2, zoom + 8)
      // We want the circle diameter to fit in the map height
      const mapHeight = map.getSize().y;
      const lat = startPoint[0];
      const metersPerPixel = (radiusMeters * 2) / (mapHeight * 0.9); // 0.8 for some padding
      const zoom = Math.log2(40075016.686 * Math.cos(lat * Math.PI / 180) / metersPerPixel) - 8;
      
      // Clamp zoom between reasonable bounds
      const clampedZoom = Math.max(6, Math.min(18, Math.floor(zoom)));
      
      // Set view to start point with calculated zoom
      map.setView([startPoint[0], startPoint[1]], clampedZoom);
      setZoom(clampedZoom);
    }
    
    prevRoutesLoaded.current = routesLoaded;
  }, [routesLoaded, startPoint, selectedMiles, map, setZoom]);

  return null;
};

const MapView: React.FC<MapViewProps> = ({ routes, selectedRouteId, startPoint, endPoint, snappedStart, snappedEnd, onMapClick, zoom, setZoom, selectedMiles, loading, routesLoaded }) => {
  // Assume selectedMiles is passed as a prop (number)
  // Show a circle for the loaded graph size when startPoint is selected
  // If you use a different prop name, adjust accordingly
  return (
    <div className="map-row">
      <div className="map-container">
        {loading && (
          <div className="loading-overlay">
            <div className="loading-spinner">
              <div className="spinner"></div>
              <p>Finding routes...</p>
            </div>
          </div>
        )}
        <MapContainer
          center={snappedStart || [40.0781, -75.2961]}
          zoom={zoom}
        >
          <ZoomListener setZoom={setZoom} />
          <MapRecenterHandler 
            startPoint={snappedStart || startPoint || null}
            selectedMiles={selectedMiles || 0}
            routesLoaded={routesLoaded || false}
            setZoom={setZoom}
          />
          <TileLayer
            url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
            attribution="&copy; OpenStreetMap contributors"
          />
          <MapClickHandler onMapClick={onMapClick} />
          {/* Show graph size circle when startPoint is selected */}
          {(() => {
            const shouldShow = startPoint && typeof selectedMiles === 'number' && selectedMiles > 0;
            return shouldShow ? (
              <Circle
                center={[startPoint[0], startPoint[1]]}
                radius={selectedMiles * 1000 * 0.5} // Approximate radius in meters (0.5 factor for better fit)
                pathOptions={{
                  color: 'red',        // Changed to red for better visibility
                  weight: 3,           // Added weight for border
                  fillColor: 'red', 
                  fillOpacity: 0.1,    // Increased opacity
                  opacity: 1           // Full opacity for border
                }}
              />
            ) : null;
          })()}
          {/* Render all routes on the map, highlight selected */}
          {routes.map(route => {
            const isSelected = route.id === selectedRouteId;
            // Extract coordinates from GeoJSON LineString
            let lineCoords: [number, number][] = [];
            if (route.geojson?.geometry?.type === 'LineString') {
                lineCoords = route.geojson.geometry.coordinates.map(
                ([lon, lat]: [number, number]) => [lat, lon]
                );
            }
            return (
                <React.Fragment key={route.id}>
                <GeoJSON
                    data={route.geojson}
                    style={{
                    color: isSelected ? 'red' : 'blue',
                    weight: isSelected ? 10 : 3,
                    opacity: isSelected ? 0.8 : 0.1,
                    }}
                />
                {/* Add directional arrows for the selected route */}
                {isSelected && lineCoords.length > 1 && (
                    <PolylineDecoratorComponent positions={lineCoords} />
                )}
                </React.Fragment>
            );
            })}
          
          {/* Render mile markers for the selected route */}
          {(() => {
            const selectedRoute = routes.find(route => route.id === selectedRouteId);
            if (!selectedRoute || !selectedRoute.mile_markers) return null;
            
            return selectedRoute.mile_markers.map((marker, index) => {
              // Create a custom icon with the mile number
              const mileIcon = L.divIcon({
                html: `<div style="
                  background-color: #fff;
                  border: 2px solid #ff4444;
                  border-radius: 50%;
                  width: 24px;
                  height: 24px;
                  display: flex;
                  align-items: center;
                  justify-content: center;
                  font-weight: bold;
                  font-size: 12px;
                  color: #ff4444;
                  box-shadow: 0 2px 4px rgba(0,0,0,0.3);
                ">${marker.mile}</div>`,
                className: 'mile-marker',
                iconSize: [24, 24],
                iconAnchor: [12, 12]
              });

              return (
                <Marker
                  key={`mile-${marker.mile}`}
                  position={[marker.coordinates[1], marker.coordinates[0]]} // Convert [lon, lat] to [lat, lon]
                  icon={mileIcon}
                >
                  <Popup>
                    <div>
                      <strong>Mile {marker.mile}</strong><br/>
                      Distance: {marker.distance_miles.toFixed(2)} mi<br/>
                      ({marker.distance_meters.toFixed(0)} m)
                    </div>
                  </Popup>
                </Marker>
              );
            });
          })()}
          {/* Show raw start point if set but not snapped yet */}
          {startPoint && !snappedStart && (
            <Marker position={[startPoint[0], startPoint[1]]}>
              <Popup>Start Point (selected)</Popup>
            </Marker>
          )}
          {/* Show raw end point if set but not snapped yet */}
          {endPoint && !snappedEnd && (
            <Marker position={[endPoint[0], endPoint[1]]}>
              <Popup>End Point (selected)</Popup>
            </Marker>
          )}
          {/* Show snapped start marker when available */}
          {snappedStart && (
            <Marker position={[snappedStart[0], snappedStart[1]]}>
              <Popup>Start Point (snapped to road)</Popup>
            </Marker>
          )}
          {/* Show snapped end marker when available */}
          {snappedEnd && (
            <Marker position={[snappedEnd[0], snappedEnd[1]]}>
              <Popup>End Point (snapped to road)</Popup>
            </Marker>
          )}
        </MapContainer>
      </div>
    </div>
  );
};

// TypeScript type fixes for leaflet-polylinedecorator
declare global {
  namespace L {
    function polylineDecorator(
      polyline: any,
      options: any
    ): any;
    namespace Symbol {
      function arrowHead(options: any): any;
    }
  }
}

const PolylineDecoratorComponent: React.FC<{ positions: [number, number][] }> = ({ positions }) => {
  const map = useMap();

  React.useEffect(() => {
    if (!map || positions.length < 2) return;

    // Create the decorator
    const decorator = (window as any).L.polylineDecorator(
      (window as any).L.polyline(positions),
      {
        patterns: [
          {
            offset: 25,
            repeat: 50,
            symbol: (window as any).L.Symbol.arrowHead({
              pixelSize: 8,
              polygon: false,
              pathOptions: { color: 'black', weight: 3, opacity: 0.4 }
            })
          }
        ]
      }
    );

    decorator.addTo(map);

    // Cleanup
    return () => {
      decorator.remove();
    };
  }, [map, positions]);

  return null;
};

export default MapView;
