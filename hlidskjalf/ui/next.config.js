/** @type {import('next').NextConfig} */
const nextConfig = {
  output: 'standalone',
  reactStrictMode: true,
  // Enable static optimization where possible
  poweredByHeader: false,
  // Custom headers for security and CORS
  async headers() {
    const corsOrigins = [
      'https://hlidskjalf.ravenhelm.test',
      'https://hlidskjalf.ravenhelm.dev',
      'https://hlidskjalf.ravenhelm.ai',
      'https://hlidskjalf-api.ravenhelm.test',
      'https://hlidskjalf-api.ravenhelm.dev',
      'https://norns.ravenhelm.test',
      'https://norns.ravenhelm.dev',
    ];
    
    return [
      {
        source: '/:path*',
        headers: [
          {
            key: 'X-Frame-Options',
            value: 'SAMEORIGIN',
          },
          {
            key: 'X-Content-Type-Options',
            value: 'nosniff',
          },
          {
            key: 'Referrer-Policy',
            value: 'strict-origin-when-cross-origin',
          },
        ],
      },
      // CORS headers for API routes
      {
        source: '/api/:path*',
        headers: [
          {
            key: 'Access-Control-Allow-Credentials',
            value: 'true',
          },
          {
            key: 'Access-Control-Allow-Methods',
            value: 'GET, POST, PUT, DELETE, PATCH, OPTIONS',
          },
          {
            key: 'Access-Control-Allow-Headers',
            value: 'Authorization, Content-Type, Accept, Origin, X-Requested-With',
          },
          {
            key: 'Access-Control-Max-Age',
            value: '86400',
          },
        ],
      },
    ];
  },
};

module.exports = nextConfig;

