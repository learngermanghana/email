export function TestimonialCard({ testimonial }: { testimonial: { name: string; role: string; quote: string } }) {
  return (
    <article className="rounded-4xl border border-white/60 bg-white/90 p-7 shadow-card backdrop-blur">
      <p className="text-base leading-8 text-charcoal/75">“{testimonial.quote}”</p>
      <div className="mt-6">
        <p className="font-semibold text-charcoal">{testimonial.name}</p>
        <p className="text-sm text-charcoal/60">{testimonial.role}</p>
      </div>
    </article>
  );
}
