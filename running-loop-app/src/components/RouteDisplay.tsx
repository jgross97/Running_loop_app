import React from 'react';
import '../styles/RouteDisplay.css';

interface RouteOption {
  id: string;
  geojson: any;
  distance: number;
  elevation_gain: number;
  error_percent?: number;
}

interface RouteDisplayProps {
  routes: RouteOption[];
  selectedRouteId: string | null;
  onSelectRoute: (id: string) => void;
}

const RouteDisplay: React.FC<RouteDisplayProps> = ({ routes, selectedRouteId, onSelectRoute }) => {
  return (
    <div>
      <h3>Route Options</h3>
      <div style={{ padding: 0 }}>
        {routes.map(route => (
          <div
            key={route.id}
            onClick={() => onSelectRoute(route.id)}
            style={{
              fontWeight: route.id === selectedRouteId ? 'bold' : 'normal',
              cursor: 'pointer',
              padding: '8px 12px',
              borderRadius: 4,
              marginBottom: 4,
              background: route.id === selectedRouteId ? '#e8f5e8' : 'transparent',
              transition: 'background 0.2s',
            }}
            onMouseEnter={e => (e.currentTarget.style.background = '#f0f8ff')}
            onMouseLeave={e => (e.currentTarget.style.background = route.id === selectedRouteId ? '#e8f5e8' : 'transparent')}
          >
            {route.id}: {route.distance.toFixed(2)} mi
            {route.error_percent !== undefined && (
              <span style={{ color: '#666', fontSize: '0.9em' }}> (±{route.error_percent.toFixed(1)}%)</span>
            )}
            , Elevation: {route.elevation_gain.toFixed(0)} ft
          </div>
        ))}
      </div>
    </div>
  );
};

export default RouteDisplay;
