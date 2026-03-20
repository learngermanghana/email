import Link from 'next/link';
import { createWhatsAppLink } from '@/lib/whatsapp';

export function MobileWhatsAppCTA() {
  return (
    <Link
      href={createWhatsAppLink('Hello Make Up & More, I want to speak with your admissions team.')}
      target="_blank"
      rel="noreferrer"
      className="fixed bottom-4 right-4 z-50 inline-flex rounded-full bg-[#25D366] px-5 py-3 text-sm font-semibold text-white shadow-soft sm:hidden"
    >
      WhatsApp Us
    </Link>
  );
}
