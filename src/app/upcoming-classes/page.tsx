import type { Metadata } from 'next';
import { SectionHeading } from '@/components/section-heading';
import { UpcomingClassesSection } from '@/components/upcoming-classes-section';

export const metadata: Metadata = {
  title: 'Upcoming Classes',
  description: 'View the next available beauty school classes, start dates, schedules, and WhatsApp reservation options for Make Up & More School of Cosmetology.'
};

export default function UpcomingClassesPage() {
  return (
    <div className="section-shell py-16 sm:py-20">
      <SectionHeading
        eyebrow="Upcoming classes"
        title="Reserve your space in an upcoming cohort."
        description="Review sample class schedules, limited-slot availability, and start dates for full programs and short courses."
      />
      <div className="mt-10">
        <UpcomingClassesSection />
      </div>
    </div>
  );
}
