import type { Metadata } from 'next';
import { RegisterForm } from '@/components/register-form';
import { SectionHeading } from '@/components/section-heading';

export const metadata: Metadata = {
  title: 'Register',
  description: 'Register your interest in beauty therapy, hairdressing, massage therapy, and other cosmetology courses in Tema through our WhatsApp-ready admissions form.'
};

export default function RegisterPage() {
  return (
    <div className="section-shell py-16 sm:py-20">
      <div className="grid gap-12 lg:grid-cols-[0.9fr_1.1fr] lg:items-start">
        <div className="space-y-6">
          <SectionHeading
            eyebrow="Registration"
            title="Take the next step toward your beauty career."
            description="Complete the form below and continue straight to WhatsApp with your details prefilled. It is a premium, low-friction admissions flow built for quick responses."
          />
          <div className="rounded-4xl border border-black/5 bg-nude/70 p-7 text-sm leading-7 text-charcoal/75 shadow-card">
            <p className="font-semibold text-charcoal">What happens next?</p>
            <ul className="mt-4 space-y-3">
              <li>• You fill in your course interest and preferred start month.</li>
              <li>• WhatsApp opens with your details prefilled for quick follow-up.</li>
              <li>• Our admissions team confirms availability and next steps.</li>
            </ul>
          </div>
        </div>
        <RegisterForm />
      </div>
    </div>
  );
}
