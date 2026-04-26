const staticExport = process.env.STATIC_EXPORT === "1";

/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  ...(staticExport
    ? {
        output: "export",
        trailingSlash: true,
        images: { unoptimized: true },
      }
    : {}),
  /**
   * Dev: give slow disks / AV scanners more time before ChunkLoadError on dynamic chunks.
   * If you still see `Loading chunk app/page failed`, stop dev, delete the `.next` folder, restart, hard-refresh (Ctrl+Shift+R).
   */
  webpack: (config, { dev, isServer }) => {
    if (dev && !isServer) {
      config.output = { ...config.output, chunkLoadTimeout: 300_000 };
    }
    return config;
  },
  /**
   * Same-origin proxy (dev / Node server only). Omitted for `STATIC_EXPORT=1` — see Next export rules.
   */
  ...(!staticExport
    ? {
        async rewrites() {
          const upstream = (process.env.API_INTERNAL_URL || "http://127.0.0.1:8000").replace(/\/$/, "");
          return [{ source: "/api-proxy/:path*", destination: `${upstream}/:path*` }];
        },
      }
    : {}),
};

export default nextConfig;
