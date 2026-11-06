import type { NextConfig } from "next";

/** Server-only: where Next.js reaches Django. Never exposed to the browser. */
const INTERNAL_API_URL = (process.env.INTERNAL_API_URL ?? "http://localhost:8000").replace(/\/$/, "");

const securityHeaders = [
  { key: "X-Content-Type-Options", value: "nosniff" },
  { key: "Referrer-Policy", value: "strict-origin-when-cross-origin" },
  { key: "X-Frame-Options", value: "DENY" },
  { key: "Permissions-Policy", value: "camera=(), microphone=(), geolocation=()" },
];

const nextConfig: NextConfig = {
  cacheComponents: true,
  partialPrefetching: true,
  poweredByHeader: false,
  // Django REST Framework URLs end in "/". Keep trailing slashes intact so POSTs to
  // /api/v1/auth/login/ aren't redirected (which would drop the request body).
  skipTrailingSlashRedirect: true,
  turbopack: {
    rules: {
      "*.css": {
        loaders: ["@tailwindcss/turbopack"],
        as: "*.css",
      },
    },
  },
  // Same-origin API: the browser calls /api/*, Next.js proxies to Django. This keeps the
  // session cookie first-party and lets Django's CSRF protection work unchanged.
  async rewrites() {
    return [
      { source: "/api/:path*/", destination: `${INTERNAL_API_URL}/api/:path*/` },
      { source: "/api/:path*", destination: `${INTERNAL_API_URL}/api/:path*` },
    ];
  },
  async headers() {
    return [{ source: "/:path*", headers: securityHeaders }];
  },
};

export default nextConfig;
