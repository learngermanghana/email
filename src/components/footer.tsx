import Link from 'next/link';
import { navigation, siteConfig } from '@/data/site';
import { createWhatsAppLink } from '@/lib/whatsapp';

export function Footer() {
  return (
    <footer className="mt-24 border-t border-black/5 bg-charcoal text-white">
      <div className="mx-auto grid max-w-7xl gap-10 px-4 py-14 sm:px-6 lg:grid-cols-[1.2fr_0.8fr_1fr] lg:px-8">
        <div className="space-y-4">
          <p className="text-xs font-semibold uppercase tracking-[0.3em] text-gold">Make Up & More</p>
          <h2 className="text-2xl font-semibold">Premium beauty training rooted in confidence, craft, and care.</h2>
          <p className="max-w-xl text-sm leading-7 text-white/70">Launch your beauty career with practical cosmetology training in Tema and explore flexible short courses designed for modern beauty professionals.</p>
        </div>
        <div>
          <h3 className="text-sm font-semibold uppercase tracking-[0.2em] text-white/70">Explore</h3>
          <ul className="mt-4 space-y-3 text-sm text-white/80">
            {navigation.map((item) => (
              <li key={item.href}>
                <Link href={item.href} className="transition hover:text-white">
                  {item.label}
                </Link>
              </li>
            ))}
          </ul>
        </div>
        <div className="space-y-4 text-sm text-white/80">
          <h3 className="font-semibold uppercase tracking-[0.2em] text-white/70">Contact</h3>
          <p>{siteConfig.location}</p>
          <p>{siteConfig.phone}</p>
          <Link href={createWhatsAppLink('Hello Make Up & More, I want to make an enquiry.')} target="_blank" rel="noreferrer" className="block transition hover:text-white">
            WhatsApp Admissions
          </Link>
          <Link href={siteConfig.instagram} target="_blank" rel="noreferrer" className="block transition hover:text-white">
            Instagram @makeupnmoreschool
          </Link>
          <Link href={siteConfig.tiktok} target="_blank" rel="noreferrer" className="block transition hover:text-white">
            TikTok @makeupnmoreschool
          </Link>
          <Link href={siteConfig.facebook} target="_blank" rel="noreferrer" className="block transition hover:text-white">
            Facebook Community
          </Link>
        </div>
      </div>
      <div className="border-t border-white/10 px-4 py-4 text-center text-xs text-white/50 sm:px-6 lg:px-8">
        © {new Date().getFullYear()} {siteConfig.name}. All rights reserved.
      </div>
    </footer>
  );
}
