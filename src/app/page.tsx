import Image from 'next/image';
import { ButtonLink } from '@/components/button-link';
import { CourseCard } from '@/components/course-card';
import { GalleryGrid } from '@/components/gallery-grid';
import { SectionHeading } from '@/components/section-heading';
import { TestimonialCard } from '@/components/testimonial-card';
import { UpcomingClassesSection } from '@/components/upcoming-classes-section';
import { courses } from '@/data/courses';
import { homepageImages } from '@/data/media-library';
import { testimonials } from '@/data/testimonials';
import { siteConfig } from '@/data/site';
import { createWhatsAppLink } from '@/lib/whatsapp';

export default function HomePage() {
  return (
    <div>
      <section className="bg-hero-glow">
        <div className="section-shell grid gap-12 py-20 lg:grid-cols-[1.05fr_0.95fr] lg:items-center lg:py-28">
          <div className="space-y-8">
            <div className="space-y-5">
              <p className="text-sm font-semibold uppercase tracking-[0.32em] text-gold">Elegant beauty education in Tema</p>
              <h1 className="max-w-3xl text-5xl font-semibold leading-tight tracking-tight text-charcoal sm:text-6xl">
                Build your beauty career with premium hands-on cosmetology training.
              </h1>
              <p className="max-w-2xl text-lg leading-8 text-charcoal/72">
                Learn beauty therapy, hairdressing, massage therapy, and short professional courses in a feminine, modern training environment designed to help you grow with confidence.
              </p>
            </div>
            <div className="flex flex-wrap gap-4">
              <ButtonLink href="/register">Register now</ButtonLink>
              <ButtonLink href={createWhatsAppLink('Hello Make Up & More, I want to register for a course.')} variant="secondary" external>
                Enquire on WhatsApp
              </ButtonLink>
            </div>
            <div className="grid gap-4 sm:grid-cols-3">
              {[
                ['7+', 'Industry-relevant course options'],
                ['Hands-on', 'Practical student-centred teaching'],
                ['Tema', 'Easy-to-find location near Princeton Academy']
              ].map(([value, label]) => (
                <div key={label} className="rounded-3xl border border-white/70 bg-white/80 p-5 shadow-card backdrop-blur">
                  <p className="text-2xl font-semibold text-charcoal">{value}</p>
                  <p className="mt-2 text-sm leading-6 text-charcoal/65">{label}</p>
                </div>
              ))}
            </div>
          </div>
          <div className="grid gap-5 lg:grid-cols-[1.2fr_0.8fr]">
            <div className="overflow-hidden rounded-[2.5rem] border border-white/70 bg-white/90 shadow-soft backdrop-blur">
              <div className="relative aspect-[4/5]">
                <Image
                  src={homepageImages.hero.src}
                  alt={homepageImages.hero.alt}
                  fill
                  priority
                  className="object-contain"
                  sizes="(min-width: 1024px) 32vw, 100vw"
                />
              </div>
            </div>
            <div className="space-y-5">
              <div className="rounded-[2rem] border border-white/70 bg-white/85 p-6 shadow-card backdrop-blur">
                <p className="text-sm font-semibold uppercase tracking-[0.3em] text-gold">Why students choose us</p>
                <div className="mt-5 space-y-4 text-charcoal/75">
                  <div>
                    <h2 className="text-2xl font-semibold text-charcoal">Refined training for modern beauty professionals.</h2>
                    <p className="mt-3 text-base leading-7">
                      Our school combines practical studio sessions, expert-led instruction, and a polished learning experience that helps students train confidently and launch beautifully.
                    </p>
                  </div>
                  <ul className="space-y-3 text-sm leading-7">
                    <li>• Small-group instruction with personal guidance.</li>
                    <li>• Premium course mix covering salon, spa, grooming, and creative skills.</li>
                    <li>• Fast WhatsApp registration flow for quick admissions support.</li>
                  </ul>
                  <ButtonLink href="/courses" variant="ghost" className="px-0 font-semibold">
                    Explore our courses →
                  </ButtonLink>
                </div>
              </div>
              <div className="grid gap-5 sm:grid-cols-2 lg:grid-cols-1 xl:grid-cols-2">
                {homepageImages.highlights.map((item) => (
                  <div key={item.title} className="overflow-hidden rounded-[2rem] border border-white/70 bg-white/80 shadow-card backdrop-blur">
                    <div className="relative aspect-[4/3]">
                      <Image src={item.src} alt={item.alt} fill className="object-cover" sizes="(min-width: 1280px) 16vw, (min-width: 640px) 50vw, 100vw" />
                    </div>
                    <div className="p-4">
                      <p className="text-sm font-semibold text-charcoal">{item.title}</p>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          </div>
        </div>
      </section>

      <section className="section-shell py-20">
        <div className="grid gap-8 lg:grid-cols-[1fr_1.05fr] lg:items-center">
          <div>
            <SectionHeading
              eyebrow="About the school"
              title="A premium cosmetology school in Tema focused on beauty, skill, and confidence."
              description={`${siteConfig.shortName} blends practical learning with a polished student experience. Our programs are designed for aspiring beauty professionals, entrepreneurs, and career changers who want elegant, industry-ready training in Ghana.`}
            />
          </div>
          <div className="overflow-hidden rounded-4xl border border-black/5 bg-white shadow-card">
            <div className="relative aspect-[16/10] bg-gradient-to-br from-blush via-white to-nude">
              <Image src={homepageImages.about.src} alt={homepageImages.about.alt} fill className="object-cover" sizes="(min-width: 1024px) 40vw, 100vw" />
            </div>
          </div>
        </div>
      </section>

      <section className="section-shell py-8">
        <SectionHeading
          eyebrow="Courses preview"
          title="Signature programs and flexible beauty short courses."
          description="From beauty therapy training in Ghana to hairdressing school pathways in Tema, our curriculum supports both career-track students and quick-skill learners."
        />
        <div className="mt-10 grid gap-6 xl:grid-cols-3">
          {courses.slice(0, 3).map((course) => (
            <CourseCard key={course.slug} course={course} />
          ))}
        </div>
        <div className="mt-8">
          <ButtonLink href="/courses" variant="secondary">View all courses</ButtonLink>
        </div>
      </section>

      <section className="mt-20 bg-section-glow py-20">
        <div className="section-shell">
          <SectionHeading
            eyebrow="Upcoming classes"
            title="Reserve your next start date with confidence."
            description="Discover upcoming cohorts for full programs and short courses, with limited slots and flexible weekday or weekend options."
          />
          <div className="mt-10">
            <UpcomingClassesSection preview />
          </div>
        </div>
      </section>

      <section className="bg-section-glow py-20">
        <div className="section-shell">
          <SectionHeading
            eyebrow="Follow our school"
            title="Stay connected through our latest beauty training updates and student highlights."
            description="Follow us on Instagram and TikTok to see practical class moments, school updates, and trend-driven beauty inspiration."
            align="center"
          />
          <div className="mt-10 grid gap-6 md:grid-cols-2">
            {[
              {
                name: 'Instagram',
                handle: '@makeupnmoreschool',
                href: siteConfig.instagram,
                copy: 'Scan the Instagram QR shared by the school or tap through here to explore visual highlights and updates.'
              },
              {
                name: 'TikTok',
                handle: '@makeupnmoreschool',
                href: siteConfig.tiktok,
                copy: 'Watch short-form beauty content, training snippets, and fresh looks from Make Up & More School.'
              }
            ].map((social) => (
              <a
                key={social.name}
                href={social.href}
                target="_blank"
                rel="noreferrer"
                className="rounded-4xl border border-black/5 bg-white p-8 shadow-card transition hover:-translate-y-1"
              >
                <p className="text-sm font-semibold uppercase tracking-[0.24em] text-gold">{social.name}</p>
                <h3 className="mt-4 text-2xl font-semibold text-charcoal">{social.handle}</h3>
                <p className="mt-3 text-sm leading-7 text-charcoal/70">{social.copy}</p>
                <p className="mt-6 font-medium text-charcoal">Visit profile →</p>
              </a>
            ))}
          </div>
        </div>
      </section>

      <section className="section-shell py-20">
        <SectionHeading
          eyebrow="Student work"
          title="A glimpse into practical sessions, polished beauty looks, and classroom energy."
          description="The gallery now reads from the dedicated public/uploads/gallery folder so future student work is simple to refresh."
        />
        <div className="mt-10">
          <GalleryGrid limit={4} />
        </div>
        <div className="mt-8">
          <ButtonLink href="/gallery" variant="secondary">Browse full gallery</ButtonLink>
        </div>
      </section>

      <section className="section-shell py-20">
        <SectionHeading
          eyebrow="Testimonials"
          title="What students and clients love about the Make Up & More experience."
          description="Social proof builds confidence and shows the elegant learning experience your school delivers."
          align="center"
        />
        <div className="mt-10 grid gap-6 lg:grid-cols-3">
          {testimonials.map((testimonial) => (
            <TestimonialCard key={testimonial.name} testimonial={testimonial} />
          ))}
        </div>
      </section>

      <section className="section-shell pb-20">
        <div className="rounded-[2.5rem] bg-charcoal px-8 py-12 text-white shadow-soft sm:px-12">
          <p className="text-sm font-semibold uppercase tracking-[0.3em] text-gold">Ready to begin?</p>
          <div className="mt-5 flex flex-col gap-6 lg:flex-row lg:items-end lg:justify-between">
            <div className="max-w-2xl">
              <h2 className="text-3xl font-semibold sm:text-4xl">Start your beauty journey with a school that feels refined, practical, and supportive.</h2>
              <p className="mt-4 text-base leading-8 text-white/70">Speak with admissions, reserve a slot, or submit your registration details today. We are ready to guide you toward the right course path.</p>
            </div>
            <div className="flex flex-wrap gap-4">
              <ButtonLink href="/register" className="bg-white text-charcoal hover:bg-nude">Register now</ButtonLink>
              <ButtonLink href="/contact" variant="ghost" className="border border-white/15 text-white hover:bg-white/10">Contact us</ButtonLink>
            </div>
          </div>
        </div>
      </section>
    </div>
  );
}
