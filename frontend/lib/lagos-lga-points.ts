/**
 * Demo centroid [lng, lat] per `lga_id` for Lagos (seed order).
 * Not survey-accurate — for map markers / choropleth demo only.
 */
export const LAGOS_LGA_POINT: Record<number, [number, number]> = {
  1: [3.317, 6.615],
  2: [3.33, 6.455],
  3: [3.29, 6.575],
  4: [3.305, 6.445],
  5: [3.36, 6.448],
  6: [2.88, 6.415],
  7: [3.48, 6.58],
  8: [3.42, 6.44],
  9: [3.52, 6.44],
  10: [3.35, 6.615],
  11: [3.35, 6.603],
  12: [3.5, 6.615],
  13: [3.39, 6.55],
  14: [3.4, 6.455],
  15: [3.38, 6.505],
  16: [3.33, 6.535],
  17: [3.12, 6.48],
  18: [3.308, 6.555],
  19: [3.38, 6.54],
  20: [3.36, 6.5],
};

export const LAGOS_VIEW: { center: [number, number]; zoom: number } = {
  center: [3.38, 6.52],
  zoom: 10,
};
