import type { Metadata } from 'next';
import { ProductCard } from '@/components/product-card';
import { SectionHeading } from '@/components/section-heading';
import { products } from '@/data/products';

export const metadata: Metadata = {
  title: 'Products',
  description: 'Explore sample beauty products and training essentials from Make Up & More School of Cosmetology, with WhatsApp enquiry options.'
};

export default function ProductsPage() {
  return (
    <div className="section-shell py-16 sm:py-20">
      <SectionHeading
        eyebrow="Products"
        title="Sample beauty and training products presented in a polished store layout."
        description="These products are sample items for now and can later be connected to Paystack, Firebase, or a dedicated commerce backend."
      />
      <p className="mt-4 inline-flex rounded-full bg-nude px-4 py-2 text-sm text-charcoal/75">Sample store items for display and enquiry purposes.</p>
      <div className="mt-10 grid gap-6 lg:grid-cols-2 xl:grid-cols-3">
        {products.map((product) => (
          <ProductCard key={product.name} product={product} />
        ))}
      </div>
    </div>
  );
}
