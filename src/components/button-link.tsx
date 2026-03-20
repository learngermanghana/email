import type { ReactNode } from 'react';
import Link from 'next/link';
import { cn } from '@/lib/utils';

type ButtonLinkProps = {
  href: string;
  children: ReactNode;
  variant?: 'primary' | 'secondary' | 'ghost';
  className?: string;
  external?: boolean;
};

const variants = {
  primary: 'bg-charcoal text-white hover:bg-charcoal/90',
  secondary: 'bg-white text-charcoal ring-1 ring-charcoal/10 hover:bg-nude/70',
  ghost: 'bg-transparent text-charcoal hover:bg-white/60'
};

export function ButtonLink({ href, children, variant = 'primary', className, external }: ButtonLinkProps) {
  return (
    <Link
      href={href}
      target={external ? '_blank' : undefined}
      rel={external ? 'noreferrer' : undefined}
      className={cn(
        'inline-flex items-center justify-center rounded-full px-6 py-3 text-sm font-medium transition duration-200',
        variants[variant],
        className
      )}
    >
      {children}
    </Link>
  );
}
