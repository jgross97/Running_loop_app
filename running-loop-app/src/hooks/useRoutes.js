import { useState, useEffect } from 'react';

/**
 * Custom hook to fetch running routes from backend based on start point and distance.
 * Handles both point-to-point routes (when endPoint is set) and loop routes (when only startPoint is set).
 * Handles loading, error, and result state.
 */
export default function useRoutes(startPoint, endPoint, distance) {
  const [routes, setRoutes] = useState([]);
  const [snappedStart, setSnappedStart] = useState(null);
  const [snappedEnd, setSnappedEnd] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  useEffect(() => {
    setRoutes([]);
    let cancelled = false;
    const controller = new AbortController();
    const fetchRoutes = async () => {
      if (!startPoint) return;
      
      setLoading(true);
      setError(null);
      
      try {
        let url;
        if (endPoint) {
          // Point-to-point route
          url = `http://localhost:8000/routes?start_lat=${startPoint[0]}&start_lon=${startPoint[1]}&end_lat=${endPoint[0]}&end_lon=${endPoint[1]}&distance_miles=${distance}`;
        } else {
          // Loop route
          url = `http://localhost:8000/loop-routes?start_lat=${startPoint[0]}&start_lon=${startPoint[1]}&distance_miles=${distance}`;
        }
        
        const res = await fetch(url, { signal: controller.signal });
        if (!res.ok) throw new Error('Failed to fetch routes');
        const data = await res.json();
        if (!cancelled) {
          // Convert distance_meters to distance (miles) for each route
          const routes = (data.routes || []).map(route => ({
            ...route,
            distance: route.distance_meters ? route.distance_meters / 1609.34 : 0,
            elevation_gain: route.elevation_gain ?? 0,
            error_percent: route.error_percent ?? 0,
          }));
          setRoutes(routes);
          setSnappedStart(data.snapped_start);
          setSnappedEnd(data.snapped_end);
        }
      } catch (err) {
        if (!cancelled && err.name !== 'AbortError') {
          setRoutes([]);
          setSnappedStart(null);
          setSnappedEnd(null);
          setError(err);
        }
      } finally {
        if (!cancelled) setLoading(false);
      }
    };
    fetchRoutes();
    return () => {
      cancelled = true;
      controller.abort();
    };
  }, [startPoint, endPoint, distance]);

  return { routes, snappedStart, snappedEnd, loading, error };
}
