"use client";

import { LAGOS_LGA_POINT, LAGOS_VIEW } from "@/lib/lagos-lga-points";
import { leadingParty, partyColor } from "@/lib/party-colors";
import type { LgaRow } from "@/lib/types";
import L from "leaflet";
import { useEffect, useMemo } from "react";
import { CircleMarker, MapContainer, Popup, TileLayer, useMap } from "react-leaflet";
import "leaflet/dist/leaflet.css";

function FixDefaultIcons() {
  useEffect(() => {
    const proto = L.Icon.Default.prototype as unknown as { _getIconUrl?: string };
    delete proto._getIconUrl;
    L.Icon.Default.mergeOptions({
      iconRetinaUrl:
        "https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/images/marker-icon-2x.png",
      iconUrl: "https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/images/marker-icon.png",
      shadowUrl: "https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/images/marker-shadow.png",
    });
  }, []);
  return null;
}

function FlyToLga({ lgaId }: { lgaId: number | null | undefined }) {
  const map = useMap();
  useEffect(() => {
    if (!lgaId) return;
    const c = LAGOS_LGA_POINT[lgaId];
    if (!c) return;
    map.flyTo([c[1], c[0]], 12, { duration: 0.8 });
  }, [lgaId, map]);
  return null;
}

function totalVotes(pr: Record<string, number>) {
  return Object.values(pr).reduce((a, b) => a + b, 0);
}

function verificationOpacity(lga: LgaRow) {
  const has = Boolean(lga.updated_at && Object.keys(lga.party_results).length);
  return has ? 0.95 : 0.22;
}

export default function LagosMapInner({
  lgas,
  focusLgaId,
}: {
  lgas: LgaRow[];
  focusLgaId?: number | null;
}) {
  const markers = useMemo(
    () =>
      lgas
        .map((l) => {
          const pt = LAGOS_LGA_POINT[l.lga_id];
          if (!pt) return null;
          const lead = leadingParty(l.party_results);
          const tv = totalVotes(l.party_results);
          const r = 7 + Math.min(16, Math.sqrt(Math.max(tv, 1)) / 4);
          return { l, pt, lead, r };
        })
        .filter(Boolean) as {
        l: LgaRow;
        pt: [number, number];
        lead: string | null;
        r: number;
      }[],
    [lgas],
  );

  return (
    <MapContainer
      center={[LAGOS_VIEW.center[1], LAGOS_VIEW.center[0]]}
      zoom={LAGOS_VIEW.zoom}
      className="h-[min(420px,55vh)] w-full rounded-lg"
      scrollWheelZoom
    >
      <FixDefaultIcons />
      <FlyToLga lgaId={focusLgaId} />
      <TileLayer
        attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OSM</a>'
        url="https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png"
      />
      {markers.map(({ l, pt, lead, r }) => (
        <CircleMarker
          key={l.lga_id}
          center={[pt[1], pt[0]]}
          radius={r}
          pathOptions={{
            color: lead ? partyColor(lead) : "#475569",
            fillColor: lead ? partyColor(lead) : "#334155",
            fillOpacity: verificationOpacity(l),
            weight: 2,
            opacity: 0.95,
          }}
        >
          <Popup className="text-slate-900">
            <div className="space-y-1 text-sm">
              <div className="font-semibold">{l.lga_name}</div>
              <div className="text-xs text-slate-600">
                {lead ? `Ahead: ${lead}` : "No totals yet"}
              </div>
              <div className="text-xs text-slate-500">
                Opacity = verification progress (rollup present)
              </div>
            </div>
          </Popup>
        </CircleMarker>
      ))}
    </MapContainer>
  );
}
