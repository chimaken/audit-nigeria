/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
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
   * Same-origin proxy: set `NEXT_PUBLIC_API_URL=/api-proxy` in `.env.local` so the
   * browser never calls `localhost:8000` directly (avoids CORS entirely).
   * `API_INTERNAL_URL` is where the Next dev server forwards those requests.
   */
  async rewrites() {
    const upstream = (process.env.API_INTERNAL_URL || "http://127.0.0.1:8000").replace(/\/$/, "");
    return [{ source: "/api-proxy/:path*", destination: `${upstream}/:path*` }];
  },
};

export default nextConfig;
