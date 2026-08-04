import type { NextConfig } from "next";

// Same-origin proxy target for the wizard's `/api/...` calls. The local runner
// (`scripts/run-local.ps1`) probes a free API port and exports
// `API_PROXY_TARGET=http://127.0.0.1:<port>` BEFORE `next build`/`next dev`,
// because Next inlines this value and generates rewrites at build/dev-server
// start — setting it afterwards has no effect. Defaults to the launcher's
// preferred port (8080) so a bare `next dev` still proxies somewhere sane.
const API_PROXY_TARGET = (process.env.API_PROXY_TARGET ?? "http://127.0.0.1:8080").replace(
  /\/$/,
  "",
);

const nextConfig: NextConfig = {
  reactStrictMode: true,
  async rewrites() {
    return [
      {
        source: "/api/:path*",
        destination: `${API_PROXY_TARGET}/api/:path*`,
      },
    ];
  },
};

export default nextConfig;
