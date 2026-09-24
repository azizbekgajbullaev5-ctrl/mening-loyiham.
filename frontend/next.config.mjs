/** @type {import('next').NextConfig} */
const backend = process.env.BACKEND_URL || "http://localhost:8000";
// STATIC_EXPORT=1 builds a static site (./out) that the backend serves itself —
// used by the Windows/no-Docker launcher so only Python is needed at runtime.
const staticExport = process.env.STATIC_EXPORT === "1";

const nextConfig = staticExport
  ? {
      output: "export",
      trailingSlash: true,
      reactStrictMode: true,
      images: { unoptimized: true },
    }
  : {
      output: "standalone",
      reactStrictMode: true,
      poweredByHeader: false,
      // The browser only talks to this origin; API calls are proxied server-side,
      // so no backend URL or API key is ever shipped to the client.
      async rewrites() {
        return [{ source: "/api/:path*", destination: `${backend}/api/:path*` }];
      },
      async headers() {
        return [
          {
            source: "/:path*",
            headers: [
              { key: "X-Content-Type-Options", value: "nosniff" },
              { key: "X-Frame-Options", value: "DENY" },
              { key: "Referrer-Policy", value: "no-referrer" },
            ],
          },
        ];
      },
      experimental: { proxyTimeout: 300000 },
    };

export default nextConfig;
