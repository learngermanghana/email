import Image from 'next/image';
import { galleryItems } from '@/data/gallery';

export function GalleryGrid({ limit }: { limit?: number }) {
  const items = limit ? galleryItems.slice(0, limit) : galleryItems;

  return (
    <div className="grid gap-6 sm:grid-cols-2 xl:grid-cols-4">
      {items.map((item) => (
        <figure key={item.title} className="overflow-hidden rounded-4xl border border-black/5 bg-white shadow-card">
          <div className="relative aspect-[4/5] bg-gradient-to-br from-white via-nude to-blush">
            <Image src={item.image} alt={item.title} fill className="object-cover transition duration-500 hover:scale-105" sizes="(min-width: 1280px) 25vw, (min-width: 640px) 50vw, 100vw" />
          </div>
          <figcaption className="space-y-2 p-5">
            <p className="text-xs font-semibold uppercase tracking-[0.2em] text-gold">{item.category}</p>
            <p className="text-base font-medium text-charcoal">{item.title}</p>
          </figcaption>
        </figure>
      ))}
    </div>
  );
}
