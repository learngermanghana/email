import { cn } from '@/lib/utils';

type SectionHeadingProps = {
  eyebrow?: string;
  title: string;
  description?: string;
  align?: 'left' | 'center';
};

export function SectionHeading({ eyebrow, title, description, align = 'left' }: SectionHeadingProps) {
  return (
    <div className={cn('space-y-4', align === 'center' && 'mx-auto max-w-3xl text-center')}>
      {eyebrow ? <p className="text-sm font-semibold uppercase tracking-[0.3em] text-gold">{eyebrow}</p> : null}
      <div className="space-y-3">
        <h2 className="text-3xl font-semibold tracking-tight text-charcoal sm:text-4xl">{title}</h2>
        {description ? <p className="text-base leading-7 text-charcoal/70 sm:text-lg">{description}</p> : null}
      </div>
    </div>
  );
}
