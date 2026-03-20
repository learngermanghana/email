import type { Metadata } from 'next';
import { GalleryGrid } from '@/components/gallery-grid';
import { SectionHeading } from '@/components/section-heading';

export const metadata: Metadata = {
  title: 'Gallery',
  description: 'Browse placeholder beauty school imagery for student practical work, bridal make-up looks, classroom training, and hair work.'
};

export default function GalleryPage() {
  return (
    <div className="section-shell py-16 sm:py-20">
      <SectionHeading
        eyebrow="Gallery"
        title="An elegant gallery layout ready for your student work and signature looks."
        description="These polished placeholder visuals are grouped into clear beauty-school categories so it is easy to swap in your own photography later."
      />
      <div className="mt-10">
        <GalleryGrid />
      </div>
    </div>
  );
}
