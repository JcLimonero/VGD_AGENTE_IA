/** @type {import('next').NextConfig} */
const upstream =
  (process.env.API_UPSTREAM_URL || process.env.NEXT_PUBLIC_API_BASE_URL || 'http://127.0.0.1:8501').replace(
    /\/+$/,
    ''
  )

const nextConfig = {
  reactStrictMode: true,
  swcMinify: true,
  images: {
    unoptimized: true,
  },
  /**
   * El navegador llama a /api/upstream/* en el mismo origen (3000) y Next reenvía al FastAPI.
   * Así no se mezclan rutas con las páginas de Next (/auth/login vs /auth/me).
   */
  async rewrites() {
    return [
      {
        source: '/api/upstream/:path*',
        destination: `${upstream}/:path*`,
      },
    ]
  },
}

module.exports = nextConfig
