import type { Metadata } from 'next';
import Link from 'next/link';
import { ContactCards } from '@/components/contact-cards';
import { SectionHeading } from '@/components/section-heading';
import { siteConfig } from '@/data/site';
import { createWhatsAppLink } from '@/lib/whatsapp';

export const metadata: Metadata = {
  title: 'Contact',
  description: 'Contact Make Up & More School of Cosmetology in Tema for admissions, WhatsApp enquiries, directions, and social links.'
};

export default function ContactPage() {
  return (
    <div className="section-shell py-16 sm:py-20">
      <SectionHeading
        eyebrow="Contact"
        title="Speak with our team, visit the school, or enquire on WhatsApp."
        description="We are easy to reach for registration support, course guidance, and general admissions questions."
      />
      <div className="mt-10">
        <ContactCards />
      </div>
      <div className="mt-12 grid gap-8 lg:grid-cols-[0.95fr_1.05fr]">
        <section className="rounded-4xl border border-black/5 bg-white p-8 shadow-card">
          <h2 className="text-2xl font-semibold text-charcoal">School details</h2>
          <dl className="mt-6 space-y-5 text-sm leading-7 text-charcoal/75">
            <div>
              <dt className="font-semibold text-charcoal">Phone</dt>
              <dd>{siteConfig.phone}</dd>
            </div>
            <div>
              <dt className="font-semibold text-charcoal">WhatsApp</dt>
              <dd>
                <Link href={createWhatsAppLink('Hello Make Up & More, I want to make an enquiry.')} target="_blank" rel="noreferrer" className="text-charcoal underline decoration-gold underline-offset-4">
                  Start a chat with admissions
                </Link>
              </dd>
            </div>
            <div>
              <dt className="font-semibold text-charcoal">Facebook</dt>
              <dd>
                <Link href={siteConfig.facebook} target="_blank" rel="noreferrer" className="text-charcoal underline decoration-gold underline-offset-4">
                  Visit our Facebook page
                </Link>
              </dd>
            </div>
            <div>
              <dt className="font-semibold text-charcoal">Location</dt>
              <dd>{siteConfig.location}</dd>
            </div>
            <div>
              <dt className="font-semibold text-charcoal">Business hours</dt>
              <dd>{siteConfig.hours.join(' • ')}</dd>
            </div>
          </dl>
        </section>
        <section className="rounded-4xl border border-dashed border-black/10 bg-nude/60 p-8 shadow-card">
          <h2 className="text-2xl font-semibold text-charcoal">Map / embed placeholder</h2>
          <div className="mt-6 flex min-h-[320px] items-center justify-center rounded-[2rem] border border-dashed border-charcoal/15 bg-white/60 p-6 text-center text-sm leading-7 text-charcoal/65">
            Replace this section with a Google Maps or other location embed when ready for production publishing.
          </div>
        </section>
      </div>
    </div>
  );
}
