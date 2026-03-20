import Link from 'next/link';
import { siteConfig } from '@/data/site';
import { createWhatsAppLink } from '@/lib/whatsapp';

const cards = [
  {
    title: 'Call admissions',
    body: siteConfig.phone,
    href: `tel:${siteConfig.phone.replace(/\s+/g, '')}`
  },
  {
    title: 'WhatsApp',
    body: 'Chat directly with our team for registration and course enquiries.',
    href: createWhatsAppLink('Hello Make Up & More, I want to make an enquiry.')
  },
  {
    title: 'Visit us',
    body: siteConfig.location,
    href: 'https://maps.google.com/?q=Near+Princeton+Academy+C25+Tema'
  }
];

export function ContactCards() {
  return (
    <div className="grid gap-6 md:grid-cols-3">
      {cards.map((card) => (
        <Link key={card.title} href={card.href} target="_blank" rel="noreferrer" className="rounded-4xl border border-black/5 bg-white p-6 shadow-card transition hover:-translate-y-1">
          <p className="text-sm font-semibold uppercase tracking-[0.2em] text-gold">{card.title}</p>
          <p className="mt-3 text-base leading-7 text-charcoal/75">{card.body}</p>
        </Link>
      ))}
    </div>
  );
}
