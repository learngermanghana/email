import Image from 'next/image';
import { Product } from '@/data/products';
import { productWhatsAppLink } from '@/lib/whatsapp';
import { ButtonLink } from './button-link';

export function ProductCard({ product }: { product: Product }) {
  return (
    <article className="overflow-hidden rounded-4xl border border-black/5 bg-white shadow-card">
      <div className="relative aspect-[4/3] bg-gradient-to-br from-blush via-white to-nude">
        <Image src={product.image} alt={product.name} fill className="object-cover" sizes="(min-width: 1024px) 33vw, (min-width: 640px) 50vw, 100vw" />
      </div>
      <div className="space-y-4 p-6">
        <div className="flex items-start justify-between gap-4">
          <h3 className="text-xl font-semibold text-charcoal">{product.name}</h3>
          <span className="rounded-full bg-nude px-4 py-2 text-sm font-medium text-charcoal">{product.price}</span>
        </div>
        <p className="text-sm leading-7 text-charcoal/70">{product.description}</p>
        <ButtonLink href={productWhatsAppLink(product.name)} external className="w-full">
          Buy / Enquire on WhatsApp
        </ButtonLink>
      </div>
    </article>
  );
}
