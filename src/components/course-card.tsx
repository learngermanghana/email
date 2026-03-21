import Image from 'next/image';
import { Course } from '@/data/courses';
import { registerWhatsAppLink } from '@/lib/whatsapp';
import { ButtonLink } from './button-link';

export function CourseCard({ course }: { course: Course }) {
  return (
    <article className="overflow-hidden rounded-4xl border border-black/5 bg-white shadow-card transition hover:-translate-y-1 hover:shadow-soft">
      <div className="relative aspect-[16/10] bg-gradient-to-br from-blush via-white to-nude">
        <Image
          src={course.image}
          alt={course.imageAlt}
          fill
          className="object-cover"
          sizes="(min-width: 1280px) 33vw, (min-width: 640px) 50vw, 100vw"
        />
      </div>
      <div className="p-7">
        <div className="flex items-start justify-between gap-4">
          <div>
            <p className="text-xs font-semibold uppercase tracking-[0.28em] text-gold">{course.category}</p>
            <h3 className="mt-3 text-2xl font-semibold text-charcoal">{course.name}</h3>
          </div>
          <span className="rounded-full bg-nude px-4 py-2 text-sm text-charcoal/80">{course.duration}</span>
        </div>
        <p className="mt-5 text-sm leading-7 text-charcoal/70">{course.summary}</p>
        {course.modules?.length ? (
          <ul className="mt-6 space-y-3 text-sm text-charcoal/80">
            {course.modules.map((module) => (
              <li key={module} className="flex items-start gap-3">
                <span className="mt-1 h-2 w-2 rounded-full bg-gold" />
                <span>{module}</span>
              </li>
            ))}
          </ul>
        ) : null}
        <div className="mt-7 flex flex-wrap gap-3">
          <ButtonLink href="/register" variant="primary">Apply now</ButtonLink>
          <ButtonLink href={registerWhatsAppLink(course.name)} variant="secondary" external>
            Ask on WhatsApp
          </ButtonLink>
        </div>
      </div>
    </article>
  );
}
