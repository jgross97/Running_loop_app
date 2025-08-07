import React from 'react';
import '../styles/RouteInfoPanel.css';

interface Route {
  id: string;
  distance: number;
  elevation_gain: number;
  error_percent?: number;
  geojson: any;
}

interface RouteInfoPanelProps {
  routes: Route[];
  selectedRouteId: string | null;
  loading: boolean;
  error: Error | null;
}

const RouteInfoPanel: React.FC<RouteInfoPanelProps> = ({ routes, selectedRouteId, loading, error }) => {
  const selectedRoute = routes.find(route => route.id === selectedRouteId);
  
  return (
    <div style={{ minHeight: 100, display: 'flex', flexDirection: 'column', justifyContent: 'center' }}>
      <h3>Route Info</h3>
      {loading ? (
        <p style={{ color: '#888' }}>Loading routes...</p>
      ) : error ? (
        <p style={{ color: '#d32f2f' }}>Error: {error.message}</p>
      ) : !selectedRoute ? (
        <p style={{ color: '#888' }}>Select a route to see details</p>
      ) : (
        <>
          <p><strong>Route:</strong> {selectedRoute.id}</p>
          <p><strong>Distance:</strong> {selectedRoute.distance.toFixed(2)} mi</p>
          <p><strong>Elevation Gain:</strong> {selectedRoute.elevation_gain.toFixed(0)} ft</p>
          {selectedRoute.error_percent !== undefined && (
            <p><strong>Target Accuracy:</strong> ±{selectedRoute.error_percent.toFixed(1)}%</p>
          )}
        </>
      )}
    </div>
  );
};

export default RouteInfoPanel;
