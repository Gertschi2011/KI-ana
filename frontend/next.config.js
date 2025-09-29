/** @type {import('next').NextConfig} */
const nextConfig = {
  output: 'standalone',
  reactStrictMode: true,
  experimental: { appDir: true },
  eslint: { ignoreDuringBuilds: true },
};
module.exports = nextConfig;
