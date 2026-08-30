/** @type {import('next').NextConfig} */
const nextConfig = {
  typescript: {
    ignoreBuildErrors: true,
  },
  images: {
    unoptimized: true,
  },
  async redirects() {
    return [
      {
        source: '/',
        destination: 'http://localhost:5173/',
        permanent: false,
      },
    ];
  },
};

export default nextConfig;
