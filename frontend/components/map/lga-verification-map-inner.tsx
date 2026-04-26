"use client";

import { canonicalStateKey, normalizeGeoName } from "@/lib/geo-centroids";
import { leadingParty, partyColor } from "@/lib/party-colors";
import type { LgaRow, NigeriaCentroidRecord } from "@/lib/types";
import L from "leaflet";
import { useQuery } from "@tanstack/react-query";
import { useEffect, useMemo, type ReactNode } from "react";
import { CircleMarker, MapContainer, Popup, TileLayer, useMap } from "react-leaflet";
import { fetchNigeriaLgaCentroids } from "@/lib/geo-centroids";
import "leaflet/dist/leaflet.css";

const NIGERIA_FALLBACK_CENTER: [number, number] = [9.082, 8.6753];
const NIGERIA_FALLBACK_ZOOM = 6;

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

function findCentroid(
  records: NigeriaCentroidRecord[],
  stateName: string,
  lgaName: string,
): NigeriaCentroidRecord | undefined {
  const ns = canonicalStateKey(stateName);
  const nl = normalizeGeoName(lgaName);
  const byState = records.find(
    (r) => canonicalStateKey(r.stateName) === ns && normalizeGeoName(r.lgaName) === nl,
  );
  if (byState) return byState;
  return records.find((r) => normalizeGeoName(r.lgaName) === nl);
}

function aggregateStateAnchors(records: NigeriaCentroidRecord[]) {
  const m = new Map<
    string,
    { sumLat: number; sumLng: number; n: number; label: string }
  >();
  for (const r of records) {
    const k = canonicalStateKey(r.stateName);
    const cur = m.get(k) ?? { sumLat: 0, sumLng: 0, n: 0, label: r.stateName };
    cur.sumLat += r.lat;
    cur.sumLng += r.lng;
    cur.n += 1;
    m.set(k, cur);
  }
  return Array.from(m.values()).map((v) => ({
    label: v.label,
    lat: v.sumLat / v.n,
    lng: v.sumLng / v.n,
  }));
}

function totalVotes(pr: Record<string, number>) {
  return Object.values(pr).reduce((a, b) => a + b, 0);
}

function verificationOpacity(lga: LgaRow) {
  const has = Boolean(lga.updated_at && Object.keys(lga.party_results).length);
  return has ? 0.95 : 0.22;
}

function FitBounds({
  latLngs,
  maxZoom,
}: {
  latLngs: [number, number][];
  maxZoom: number;
}) {
  const map = useMap();
  useEffect(() => {
    if (!latLngs.length) return;
    if (latLngs.length === 1) {
      map.setView(latLngs[0], Math.min(maxZoom, 9));
      return;
    }
    const b = L.latLngBounds(latLngs);
    map.fitBounds(b, { padding: [28, 28], maxZoom });
  }, [latLngs, map, maxZoom]);
  return null;
}

function FlyToLga({
  focusLgaId,
  lgas,
  records,
  stateName,
}: {
  focusLgaId: number | null | undefined;
  lgas: LgaRow[];
  records: NigeriaCentroidRecord[];
  stateName: string;
}) {
  const map = useMap();
  useEffect(() => {
    if (!focusLgaId) return;
    const row = lgas.find((l) => l.lga_id === focusLgaId);
    if (!row) return;
    const c = findCentroid(records, stateName, row.lga_name);
    if (!c) return;
    map.flyTo([c.lat, c.lng], 11, { duration: 0.85 });
  }, [focusLgaId, lgas, map, records, stateName]);
  return null;
}

export type LgaVerificationMapInnerProps =
  | { mode: "national" }
  | { mode: "state"; stateName: string; lgas: LgaRow[]; focusLgaId?: number | null };

export default function LgaVerificationMapInner(props: LgaVerificationMapInnerProps) {
  const { data: payload, isLoading, error } = useQuery({
    queryKey: ["geo", "nigeria-lga-centroids"],
    queryFn: fetchNigeriaLgaCentroids,
    staleTime: Infinity,
  });

  const records = payload?.records ?? [];

  const { markers, fitPoints, maxZoom } = useMemo(() => {
    if (!records.length) {
      return { markers: [] as ReactNode[], fitPoints: [] as [number, number][], maxZoom: 6 };
    }
    if (props.mode === "national") {
      const anchors = aggregateStateAnchors(records);
      const pts: [number, number][] = anchors.map((a) => [a.lat, a.lng]);
      const mk: ReactNode[] = anchors.map((a) => (
        <CircleMarker
          key={a.label}
          center={[a.lat, a.lng]}
          radius={9}
          pathOptions={{
            color: "#64748b",
            fillColor: "#334155",
            fillOpacity: 0.75,
            weight: 2,
            opacity: 0.95,
          }}
        >
          <Popup className="text-slate-900">
            <div className="text-sm font-medium">{a.label}</div>
            <div className="text-xs text-slate-600">Pick a state above to see local areas on the map.</div>
          </Popup>
        </CircleMarker>
      ));
      return { markers: mk, fitPoints: pts, maxZoom: 6 };
    }
    const { stateName, lgas } = props;
    const pts: [number, number][] = [];
    const mk: ReactNode[] = [];
    for (const l of lgas) {
      const c = findCentroid(records, stateName, l.lga_name);
      if (!c) continue;
      pts.push([c.lat, c.lng]);
      const lead = leadingParty(l.party_results);
      const tv = totalVotes(l.party_results);
      const r = 7 + Math.min(16, Math.sqrt(Math.max(tv, 1)) / 4);
      mk.push(
        <CircleMarker
          key={l.lga_id}
          center={[c.lat, c.lng]}
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
              <div className="text-xs text-slate-600">{lead ? `Ahead: ${lead}` : "No totals yet"}</div>
            </div>
          </Popup>
        </CircleMarker>,
      );
    }
    return { markers: mk, fitPoints: pts, maxZoom: 11 };
  }, [props, records]);

  if (isLoading) {
    return (
      <div className="flex h-[min(420px,55vh)] w-full items-center justify-center rounded-lg border border-command-border bg-command-panel text-sm text-slate-500">
        Loading map…
      </div>
    );
  }
  if (error) {
    return (
      <div className="flex h-[min(420px,55vh)] w-full items-center justify-center rounded-lg border border-amber-900/40 bg-amber-950/20 px-4 text-center text-sm text-amber-200">
        {String(error)}
      </div>
    );
  }

  return (
    <MapContainer
      center={NIGERIA_FALLBACK_CENTER}
      zoom={NIGERIA_FALLBACK_ZOOM}
      className="h-[min(420px,55vh)] w-full rounded-lg"
      scrollWheelZoom
    >
      <FixDefaultIcons />
      {fitPoints.length ? <FitBounds latLngs={fitPoints} maxZoom={maxZoom} /> : null}
      {props.mode === "state" && props.focusLgaId ? (
        <FlyToLga
          focusLgaId={props.focusLgaId}
          lgas={props.lgas}
          records={records}
          stateName={props.stateName}
        />
      ) : null}
      <TileLayer
        attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OSM</a>'
        url="https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png"
      />
      {markers}
    </MapContainer>
  );
}
