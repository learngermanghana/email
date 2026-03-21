import type { Metadata } from 'next';
import { GalleryGrid } from '@/components/gallery-grid';
import { SectionHeading } from '@/components/section-heading';

export const metadata: Metadata = {
  title: 'Gallery',
  description: 'Browse beauty school imagery for student practical work, bridal make-up looks, classroom training, and hair work.'
};

export default function GalleryPage() {
  return (
    <div className="section-shell py-16 sm:py-20">
      <SectionHeading
        eyebrow="Gallery"
        title="An elegant gallery layout ready for your student work and signature looks."
        description="Gallery cards now read from public/uploads/gallery, so you can refresh school photography by replacing image files in one place."
      />
      <div className="mt-10">
        <GalleryGrid />
      </div>
    </div>
  );
}
