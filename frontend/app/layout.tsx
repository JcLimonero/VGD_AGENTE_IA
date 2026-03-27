import type { Metadata } from 'next'
import './globals.css'
import { AuthHydrator } from '@/components/AuthHydrator'
import { ThemePreferenceBridge } from '@/components/ThemePreferenceBridge'

export const metadata: Metadata = {
  title: 'VGD Agente IA - Dashboard',
  description: 'Dashboard inteligente para consultas DWH con agente IA',
}

export default function RootLayout({
  children,
}: {
  children: React.ReactNode
}) {
  return (
    <html lang="es">
      <body suppressHydrationWarning>
        <ThemePreferenceBridge />
        <AuthHydrator />
        {children}
      </body>
    </html>
  )
}

