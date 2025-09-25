/** @type {import('next').NextConfig} */
const nextConfig = {
  experimental: {},
  async rewrites() {
    const raw = process.env.API_BASE || process.env.NEXT_PUBLIC_API_BASE || ''
    const stripped = raw.replace(/\/+$/, '')
    if (!stripped) return []
    const base = /^https?:\/\//i.test(stripped) ? stripped : `https://${stripped}`
    return [
      {
        source: '/api/:path*',
        destination: `${base}/api/:path*`,
      },
      {
        source: '/upstream/:path*',
        destination: `${base}/api/:path*`,
      },
    ]
  },
}
export default nextConfig
