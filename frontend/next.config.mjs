/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  async rewrites() {
    return [
      {
        source: "/api/:path*",
        destination: "http://127.0.0.1:8000/api/:path*",
      },
      {
        source: "/sms/:path*",
        destination: "http://127.0.0.1:8000/sms/:path*",
      },
      {
        source: "/voice/:path*",
        destination: "http://127.0.0.1:8000/voice/:path*",
      },
    ];
  },
};

export default nextConfig;
