import { ButtonLink } from '@/components/button-link';
import { CourseCard } from '@/components/course-card';
import { GalleryGrid } from '@/components/gallery-grid';
import { ProductCard } from '@/components/product-card';
import { SectionHeading } from '@/components/section-heading';
import { TestimonialCard } from '@/components/testimonial-card';
import { UpcomingClassesSection } from '@/components/upcoming-classes-section';
import { courses } from '@/data/courses';
import { products } from '@/data/products';
import { testimonials } from '@/data/testimonials';
import { siteConfig } from '@/data/site';
import { createWhatsAppLink } from '@/lib/whatsapp';

export default function HomePage() {
  return (
    <div>
      <section className="bg-hero-glow">
        <div className="section-shell grid gap-12 py-20 lg:grid-cols-[1.15fr_0.85fr] lg:items-center lg:py-28">
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
          <div className="rounded-[2.5rem] border border-white/70 bg-white/80 p-8 shadow-soft backdrop-blur">
            <div className="rounded-[2rem] bg-gradient-to-br from-blush via-white to-nude p-8">
              <p className="text-sm font-semibold uppercase tracking-[0.3em] text-gold">Why students choose us</p>
              <div className="mt-6 space-y-5 text-charcoal/75">
                <div>
                  <h2 className="text-2xl font-semibold text-charcoal">Refined training for modern beauty professionals.</h2>
                  <p className="mt-3 text-base leading-7">Our school combines practical studio sessions, expert-led instruction, and a polished learning experience that helps students train confidently and launch beautifully.</p>
                </div>
                <ul className="space-y-4 text-sm leading-7">
                  <li>• Small-group instruction with personal guidance.</li>
                  <li>• Premium course mix covering salon, spa, grooming, and creative skills.</li>
                  <li>• Fast WhatsApp registration flow for quick admissions support.</li>
                </ul>
                <ButtonLink href="/courses" variant="ghost" className="px-0 font-semibold">
                  Explore our courses →
                </ButtonLink>
              </div>
            </div>
          </div>
        </div>
      </section>

      <section className="section-shell py-20">
        <SectionHeading
          eyebrow="About the school"
          title="A premium cosmetology school in Tema focused on beauty, skill, and confidence."
          description={`${siteConfig.shortName} blends practical learning with a polished student experience. Our programs are designed for aspiring beauty professionals, entrepreneurs, and career changers who want elegant, industry-ready training in Ghana.`}
        />
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

      <section className="section-shell py-20">
        <SectionHeading
          eyebrow="Why choose us"
          title="A calm, polished learning environment designed for growth."
          description="We balance professionalism and warmth with structured practical work, supportive tutors, and business-ready beauty education."
          align="center"
        />
        <div className="mt-10 grid gap-6 md:grid-cols-3">
          {[
            ['Practical first', 'Hands-on demonstrations and student practice are woven into every program.'],
            ['Career-focused', 'Courses help students prepare for salon work, freelance services, and entrepreneurial growth.'],
            ['Easy support', 'Quick WhatsApp admissions and enquiry flows make it easy to connect with our team.']
          ].map(([title, copy]) => (
            <article key={title} className="rounded-4xl border border-black/5 bg-white p-8 text-center shadow-card">
              <div className="mx-auto h-14 w-14 rounded-2xl bg-blush" />
              <h3 className="mt-6 text-xl font-semibold text-charcoal">{title}</h3>
              <p className="mt-3 text-sm leading-7 text-charcoal/70">{copy}</p>
            </article>
          ))}
        </div>
      </section>

      <section className="section-shell py-20">
        <SectionHeading
          eyebrow="Student work"
          title="A glimpse into practical sessions, polished beauty looks, and classroom energy."
          description="The gallery is structured so you can easily replace the current placeholder visuals with future student work and school photography."
        />
        <div className="mt-10">
          <GalleryGrid limit={4} />
        </div>
        <div className="mt-8">
          <ButtonLink href="/gallery" variant="secondary">Browse full gallery</ButtonLink>
        </div>
      </section>

      <section className="bg-section-glow py-20">
        <div className="section-shell">
          <SectionHeading
            eyebrow="Products preview"
            title="Sample beauty products students and clients can enquire about."
            description="This sample product section is ready to evolve into a fuller store experience later, with Paystack or Firebase integrations when you are ready."
          />
          <div className="mt-10 grid gap-6 lg:grid-cols-3">
            {products.slice(0, 3).map((product) => (
              <ProductCard key={product.name} product={product} />
            ))}
          </div>
          <div className="mt-8">
            <ButtonLink href="/products" variant="secondary">View sample products</ButtonLink>
          </div>
        </div>
      </section>

      <section className="section-shell py-20">
        <SectionHeading
          eyebrow="Testimonials"
          title="What students love about the experience."
          description="These testimonials are sample content and can be replaced with verified student stories later."
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
