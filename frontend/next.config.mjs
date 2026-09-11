/** @type {import('next').NextConfig} */
let rawBackendUrl = process.env.BACKEND_URL || "http://127.0.0.1:8000";
if (!rawBackendUrl.startsWith("http://") && !rawBackendUrl.startsWith("https://")) {
  rawBackendUrl = `https://${rawBackendUrl}`;
}
const backendUrl = rawBackendUrl.replace(/\/$/, "");

const nextConfig = {
  reactStrictMode: true,
  async rewrites() {
    return [
      {
        source: "/api/:path*",
        destination: `${backendUrl}/api/:path*`,
      },
      {
        source: "/sms/:path*",
        destination: `${backendUrl}/sms/:path*`,
      },
      {
        source: "/voice/:path*",
        destination: `${backendUrl}/voice/:path*`,
      },
    ];
  },
};

export default nextConfig;
