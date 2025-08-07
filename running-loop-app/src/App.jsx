import React, { useState, useEffect } from "react";
import "./App.css";
import RouteSelector from "./components/RouteSelector";
import MapView from "./components/MapView";
import ElevationGraph from "./components/ElevationGraph";
import RouteDisplay from "./components/RouteDisplay";
import RouteInfoPanel from "./components/RouteInfoPanel";
import useRoutes from "./hooks/useRoutes";

// Default map center (lat, lon)
const DEFAULT_CENTER = {
  center: [40.07953808391153, -75.2955508853578],
  dist: 2000,
};

function App() {
  // Track start, end, and pending (last clicked) point
  const [startPoint, setStartPoint] = useState(null);
  const [endPoint, setEndPoint] = useState(null);
  const [pendingPoint, setPendingPoint] = useState(null);
  const [distance, setDistance] = useState(5);
  const [selectedRouteId, setSelectedRouteId] = useState(null);
  const [settingMode, setSettingMode] = useState(null); // 'start' or 'end'
  const [zoom, setZoom] = useState(16);
  const [routesLoaded, setRoutesLoaded] = useState(false);

  // Preload the backend graph on initial mount (one-time effect)
  useEffect(() => {
    fetch("http://localhost:8000/preload", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(DEFAULT_CENTER),
    });
  }, []);

  // Only request routes if start is set (for loops) or both start and end are set (for point-to-point)
  const { routes, snappedStart, snappedEnd, loading, error } = useRoutes(
    startPoint,
    endPoint,
    distance
  );

  // Determine if we're in loop mode (only start point set) or point-to-point mode
  const isLoopMode = startPoint && !endPoint;

  // When routes change, auto-select the first route if available
  useEffect(() => {
    if (routes.length > 0) {
      setSelectedRouteId(routes[0].id);
    } else {
      setSelectedRouteId(null);
    }
  }, [routes]);

  // Track when routes are loaded (when loading finishes and routes are available)
  useEffect(() => {
    if (routes.length > 0 && !loading) {
      setRoutesLoaded(true);
    }
  }, [routes, loading]);

  // Reset routesLoaded when starting new search
  useEffect(() => {
    if (loading) {
      setRoutesLoaded(false);
    }
  }, [loading]);

  // Handle map click based on current setting mode
  const handleMapClick = (lat, lon) => {
    if (loading) return;

    if (settingMode === "start") {
      setStartPoint([lat, lon]);
      setSettingMode(null); // Exit setting mode
    } else if (settingMode === "end") {
      setEndPoint([lat, lon]);
      setSettingMode(null); // Exit setting mode
    }
  };

  // Enter start/end setting mode
  const handleStartSettingMode = () => {
    setSettingMode("start");
  };

  const handleEndSettingMode = () => {
    setSettingMode("end");
  };

  // Clear start or end points
  const handleClearStart = () => {
    setStartPoint(null);
  };

  const handleClearEnd = () => {
    setEndPoint(null);
  };

  // Handle distance change from RouteSelector
  const handleDistanceChange = (d) => {
    setDistance(d);
  };

  // Handle route selection from RouteDisplay
  const handleSelectRoute = (id) => {
    setSelectedRouteId(id);
  };

  return (
    <div className="App">
      <h1>Running Loop App</h1>

      {/* Mode indicator */}
      <div
        style={{
          marginBottom: 8,
          padding: 8,
          backgroundColor: isLoopMode ? "#e8f5e8" : "#f0f8ff",
          borderRadius: 4,
        }}
      >
        <strong>Mode: </strong>
        {isLoopMode
          ? "🔄 Loop Routes (start = end)"
          : "🎯 Point-to-Point Routes"}
        {startPoint && !endPoint && (
          <span style={{ marginLeft: 8, fontSize: "0.9em", color: "#666" }}>
            - Set an end point for point-to-point routes, or adjust distance for
            loop routes
          </span>
        )}
      </div>

      <div style={{ marginBottom: 12 }}>
        <button
          onClick={handleStartSettingMode}
          disabled={loading || settingMode === "start"}
          style={{ backgroundColor: settingMode === "start" ? "#4CAF50" : "" }}
        >
          {settingMode === "start" ? "Click Map for Start" : "Set Start Point"}
        </button>
        <button
          onClick={handleEndSettingMode}
          disabled={loading || settingMode === "end"}
          style={{
            backgroundColor: settingMode === "end" ? "#4CAF50" : "",
            marginLeft: 8,
          }}
        >
          {settingMode === "end"
            ? "Click Map for End"
            : "Set End Point (Optional)"}
        </button>
        {startPoint && (
          <button onClick={handleClearStart} style={{ marginLeft: 8 }}>
            Clear Start
          </button>
        )}
        {endPoint && (
          <button onClick={handleClearEnd} style={{ marginLeft: 8 }}>
            Clear End
          </button>
        )}
      </div>

      <div
        style={{
          display: "flex",
          flexDirection: "row",
          alignItems: "flex-start",
          justifyContent: "flex-start",
          gap: 5,
          maxWidth: "100%",
        }}
      >
        <div style={{ maxWidth: "300px", flexShrink: 0 }}>
          <RouteSelector
            startPoint={startPoint}
            endPoint={endPoint}
            onStartPointChange={(lat, lon) => setStartPoint([lat, lon])}
            onEndPointChange={(lat, lon) => setEndPoint([lat, lon])}
            distance={distance}
            onDistanceChange={handleDistanceChange}
          />
          <RouteDisplay
            routes={routes}
            selectedRouteId={selectedRouteId}
            onSelectRoute={handleSelectRoute}
          />
          <RouteInfoPanel
            routes={routes}
            selectedRouteId={selectedRouteId}
            loading={loading}
            error={error}
          />
        </div>
        <div
          style={{
            display: "flex",
            flexDirection: "column",
            alignItems: "center",
            width: "100%",
          }}
        >
          <MapView
            routes={routes}
            selectedRouteId={selectedRouteId}
            startPoint={startPoint}
            endPoint={endPoint}
            snappedStart={snappedStart}
            snappedEnd={snappedEnd}
            onMapClick={handleMapClick}
            zoom={zoom}
            setZoom={setZoom}
            selectedMiles={distance}
            loading={loading}
            routesLoaded={routesLoaded}
          />
          <ElevationGraph
            elevationProfile={
              selectedRouteId && routes.length > 0
                ? routes.find((route) => route.id === selectedRouteId)
                    ?.smoothed_elevation_profile || null
                : null
            }
            maxElevation={
              selectedRouteId && routes.length > 0
                ? routes.find((route) => route.id === selectedRouteId)
                    ?.max_elevation
                : undefined
            }
            minElevation={
              selectedRouteId && routes.length > 0
                ? routes.find((route) => route.id === selectedRouteId)
                    ?.min_elevation
                : undefined
            }
            totalDistance={
              selectedRouteId && routes.length > 0
                ? routes.find((route) => route.id === selectedRouteId)?.distance
                : undefined
            }
            routeId={selectedRouteId}
          />
        </div>
      </div>
    </div>
  );
}

export default App;
