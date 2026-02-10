import type { AppProps } from 'next/app'
import '@/app/globals.css'
import { Inter } from 'next/font/google'

const inter = Inter({ subsets: ['latin'] })

import { ThemeProvider } from '@/lib/context/ThemeContext'
import { LayoutProvider } from '@/lib/context/LayoutContext'
import { MerchantProvider } from '@/lib/context/MerchantContext'

export default function App({ Component, pageProps }: AppProps) {
  return (
    <ThemeProvider>
      <MerchantProvider>
        <LayoutProvider>
          <div className={inter.className}>
            <Component {...pageProps} />
          </div>
        </LayoutProvider>
      </MerchantProvider>
    </ThemeProvider>
  )
}

