/** @type {import('next').NextConfig} */
const nextConfig = {
  // App is served under its own subdomain (app.ki-ana.at), no basePath needed
  reactStrictMode: true,
  poweredByHeader: false,
  // Remove unsupported/legacy flags
  experimental: {},
  eslint: { ignoreDuringBuilds: true },
};
module.exports = nextConfig;
