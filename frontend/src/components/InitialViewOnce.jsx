import { useEffect, useRef } from 'react';
import { useMap } from 'react-leaflet';

export default function InitialViewOnce({ center, zoom, forceUpdateTrigger }) {
  const map = useMap();
  const hasRun = useRef(false);

  useEffect(() => {
    // Run on initial mount
    if (!hasRun.current && center) {
      map.setView(center, zoom, { animate: false });
      hasRun.current = true;
    }
  }, [center, zoom, map]);

  useEffect(() => {
    // Run ONLY when "Use My Location" is explicitly clicked and resolves
    if (forceUpdateTrigger && center) {
      map.setView(center, zoom, { animate: true, duration: 1 });
    }
  }, [forceUpdateTrigger, center, zoom, map]);

  return null;
}
