import React, { useMemo } from 'react';
import {
  AreaChart,
  Area,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
} from 'recharts';
import '../styles/ElevationGraph.css';

interface ElevationGraphProps {
  elevationProfile: number[] | null;
  maxElevation?: number;
  minElevation?: number;
  routeId?: string;
  totalDistance?: number; // Total distance in miles
}

const ElevationGraph: React.FC<ElevationGraphProps> = ({ 
  elevationProfile, 
  maxElevation, 
  minElevation, 
  routeId,
  totalDistance 
}) => {
  // Transform elevation data for Recharts
  const chartData = useMemo(() => {
    if (!elevationProfile || elevationProfile.length === 0) {
      return [];
    }

    return elevationProfile.map((elevation, index) => {
      const progressRatio = index / (elevationProfile.length - 1);
      const actualDistance = totalDistance ? (progressRatio * totalDistance) : (progressRatio * 100);
      
      return {
        distance: totalDistance ? actualDistance.toFixed(2) : `${(progressRatio * 100).toFixed(1)}%`,
        distanceValue: actualDistance, // Numeric value for sorting/calculations
        elevation: Math.round(elevation),
        elevationRaw: elevation, // Keep raw for calculations
      };
    });
  }, [elevationProfile, totalDistance]);

  // Calculate elevation statistics
  const elevationStats = useMemo(() => {
    if (!elevationProfile || elevationProfile.length === 0) {
      return { min: 0, max: 0, gain: 0 };
    }

    const min = minElevation ?? Math.min(...elevationProfile);
    const max = maxElevation ?? Math.max(...elevationProfile);
    const gain = max - min;

    return { min, max, gain };
  }, [elevationProfile, maxElevation, minElevation]);

  // Custom tooltip component
  const CustomTooltip = ({ active, payload, label }: any) => {
    if (active && payload && payload.length) {
      return (
        <div className="elevation-tooltip">
          <p className="tooltip-label">
            {totalDistance 
              ? `Distance: ${label} mi` 
              : `Distance: ${label}%`
            }
          </p>
          <p className="tooltip-value">
            <span className="tooltip-color" style={{ backgroundColor: '#ff4444' }}></span>
            {`Elevation: ${payload[0].value}ft`}
          </p>
        </div>
      );
    }
    return null;
  };

  if (!elevationProfile || elevationProfile.length === 0) {
    return (
      <div className="elevation-graph-container">
        <div className="elevation-graph-empty">
          <p>No elevation data available for selected route</p>
        </div>
      </div>
    );
  }

  return (
    <div className="elevation-graph-container">
      <div className="elevation-graph-header">
        <h3>Elevation Profile</h3>
        <div className="elevation-stats">
          <span>Min: {Math.round(elevationStats.min)}ft</span>
          <span>Max: {Math.round(elevationStats.max)}ft</span>
          <span>Gain: {Math.round(elevationStats.gain)}ft</span>
        </div>
      </div>
      <div className="elevation-graph-chart-container">
        <ResponsiveContainer width="100%" height={250}>
          <AreaChart
            data={chartData}
            margin={{
              top: 10,
              right: 30,
              left: 0,
              bottom: 0,
            }}
          >
            <defs>
              <linearGradient id="elevationGradient" x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%" stopColor="#ff4444" stopOpacity={0.4} />
                <stop offset="100%" stopColor="#ff4444" stopOpacity={0.05} />
              </linearGradient>
            </defs>
            <CartesianGrid strokeDasharray="3 3" stroke="#e0e0e0" strokeOpacity={0.5} />
            <XAxis 
              dataKey="distance" 
              axisLine={false}
              tickLine={false}
              tick={{ fontSize: 12, fill: '#666' }}
              tickFormatter={(value) => totalDistance ? `${value}mi` : `${value}%`}
            />
            <YAxis 
              axisLine={false}
              tickLine={false}
              tick={{ fontSize: 12, fill: '#666' }}
              tickFormatter={(value) => `${value}ft`}
              domain={['dataMin - 10', 'dataMax + 10']}
            />
            <Tooltip content={<CustomTooltip />} />
            <Area
              type="monotone"
              dataKey="elevation"
              stroke="#ff4444"
              strokeWidth={2}
              fill="url(#elevationGradient)"
              dot={false}
              activeDot={{ r: 4, stroke: '#ff4444', strokeWidth: 2, fill: '#fff' }}
            />
          </AreaChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
};

export default ElevationGraph;
