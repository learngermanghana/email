import type { Metadata } from 'next';
import type { ReactNode } from 'react';
import './globals.css';
import { Header } from '@/components/header';
import { Footer } from '@/components/footer';
import { MobileWhatsAppCTA } from '@/components/mobile-whatsapp-cta';
import { siteConfig } from '@/data/site';

export const metadata: Metadata = {
  metadataBase: new URL('https://makeup-and-more-school.vercel.app'),
  title: {
    default: `${siteConfig.name} | Premium Beauty Training in Tema`,
    template: `%s | ${siteConfig.shortName}`
  },
  description: siteConfig.description,
  keywords: siteConfig.keywords,
  openGraph: {
    title: siteConfig.name,
    description: siteConfig.description,
    type: 'website',
    locale: 'en_GH',
    siteName: siteConfig.name
  },
  twitter: {
    card: 'summary_large_image',
    title: siteConfig.name,
    description: siteConfig.description
  }
};

export default function RootLayout({ children }: Readonly<{ children: ReactNode }>) {
  return (
    <html lang="en">
      <body>
        <Header />
        <main>{children}</main>
        <Footer />
        <MobileWhatsAppCTA />
      </body>
    </html>
  );
}
