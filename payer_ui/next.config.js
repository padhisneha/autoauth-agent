/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  async rewrites() {
    return [
      {
        source: '/payer-api/:path*',
        destination: 'http://localhost:8001/:path*',
      },
    ];
  },
};

module.exports = nextConfig;
