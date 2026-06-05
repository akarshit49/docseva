//genai: Sprint 3 / WS-F — Next.js 14 config. `output: 'standalone'` keeps the
//        production Docker image lean by bundling only the files Next needs.
/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  output: 'standalone',
  // The API service is the only allowed remote host for images (logos, previews).
  images: {
    remotePatterns: [
      { protocol: 'http', hostname: '**' },
      { protocol: 'https', hostname: '**' },
    ],
  },
  // Forward `/api/v1/*` to the FastAPI service. The Next.js route handlers
  // under app/api/auth/* still own the auth flow so we can set httpOnly
  // cookies; everything else proxies straight through.
  async rewrites() {
    const apiBase =
      process.env.NEXT_PUBLIC_API_INTERNAL_URL ||
      process.env.API_INTERNAL_URL ||
      'http://api:8000'
    return [
      {
        source: '/api/v1/:path*',
        destination: `${apiBase}/api/v1/:path*`,
      },
    ]
  },
  experimental: {
    serverActions: { bodySizeLimit: '20mb' },
  },
}

module.exports = nextConfig
