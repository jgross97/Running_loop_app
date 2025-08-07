import React from 'react';
import '../styles/RouteSelector.css';


interface RouteSelectorProps {
  startPoint: [number, number] | null;
  endPoint: [number, number] | null;
  onStartPointChange: (lat: number, lon: number) => void;
  onEndPointChange: (lat: number, lon: number) => void;
  distance: number;
  onDistanceChange: (distance: number) => void;
}


const RouteSelector: React.FC<RouteSelectorProps> = ({ startPoint, endPoint, distance, onStartPointChange, onEndPointChange, onDistanceChange }) => {
  return (
    <div style={{ padding: '12px 16px', background: '#f8f8fa', borderRadius: 8, boxShadow: '0 1px 4px rgba(0,0,0,0.06)', maxWidth: '100%' }}>
      <h3 style={{ marginBottom: 12, fontWeight: 600, fontSize: '1.1em', color: '#333' }}>Set Route Distance (miles)</h3>
      <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
        <input
          type="number"
          min={1}
          max={20}
          step={1}
          value={distance}
          onChange={e => onDistanceChange(Number(e.target.value))}
          style={{ width: 70, padding: '6px 10px', fontSize: '1em', borderRadius: 4, border: '1px solid #ccc', marginRight: 4 }}
        />
        <span style={{ fontSize: '1em', color: '#555' }}>mi</span>
      </div>
    </div>
  );
};

export default RouteSelector;
