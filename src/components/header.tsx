'use client';

import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { navigation, siteConfig } from '@/data/site';
import { cn } from '@/lib/utils';
import { createWhatsAppLink } from '@/lib/whatsapp';

export function Header() {
  const pathname = usePathname();

  return (
    <header className="sticky top-0 z-50 border-b border-white/70 bg-white/85 backdrop-blur-xl">
      <div className="mx-auto flex max-w-7xl items-center justify-between gap-4 px-4 py-4 sm:px-6 lg:px-8">
        <Link href="/" className="max-w-xs">
          <span className="block text-xs font-semibold uppercase tracking-[0.32em] text-gold">Tema, Ghana</span>
          <span className="text-lg font-semibold tracking-tight text-charcoal sm:text-xl">{siteConfig.shortName}</span>
          <span className="block text-xs text-charcoal/60">School of Cosmetology</span>
        </Link>
        <nav aria-label="Primary navigation" className="hidden items-center gap-1 lg:flex">
          {navigation.map((item) => (
            <Link
              key={item.href}
              href={item.href}
              className={cn(
                'rounded-full px-4 py-2 text-sm transition hover:bg-nude hover:text-charcoal',
                pathname === item.href ? 'bg-nude text-charcoal' : 'text-charcoal/70'
              )}
            >
              {item.label}
            </Link>
          ))}
        </nav>
        <Link
          href={createWhatsAppLink('Hello Make Up & More, I would like to speak with your admissions team.')}
          target="_blank"
          rel="noreferrer"
          className="hidden rounded-full bg-charcoal px-5 py-3 text-sm font-medium text-white transition hover:bg-charcoal/90 sm:inline-flex"
        >
          Chat on WhatsApp
        </Link>
      </div>
      <nav aria-label="Mobile navigation" className="border-t border-black/5 px-4 py-3 lg:hidden">
        <div className="flex gap-2 overflow-x-auto pb-1">
          {navigation.map((item) => (
            <Link
              key={item.href}
              href={item.href}
              className={cn(
                'whitespace-nowrap rounded-full px-4 py-2 text-sm transition',
                pathname === item.href ? 'bg-charcoal text-white' : 'bg-nude text-charcoal/80'
              )}
            >
              {item.label}
            </Link>
          ))}
        </div>
      </nav>
    </header>
  );
}
