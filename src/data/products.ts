export type Product = {
  name: string;
  image: string;
  description: string;
  price: string;
};

export const products: Product[] = [
  {
    name: 'Radiance Facial Kit',
    image: '/images/product-facial-kit.svg',
    description: 'A classroom favourite skincare set for cleansing, exfoliating, and finishing facials.',
    price: 'GH₵ 240'
  },
  {
    name: 'Pro Brush Collection',
    image: '/images/product-brushes.svg',
    description: 'Premium multi-use brushes for flawless beauty therapy and make-up application.',
    price: 'GH₵ 180'
  },
  {
    name: 'Nail Prep Essentials',
    image: '/images/product-nails.svg',
    description: 'A polished starter bundle for manicures, pedicures, and salon-ready nail prep.',
    price: 'GH₵ 130'
  },
  {
    name: 'Luxury Hair Care Duo',
    image: '/images/product-haircare.svg',
    description: 'Hydrating shampoo and treatment pair designed for healthy styling practice.',
    price: 'GH₵ 160'
  },
  {
    name: 'Massage Therapy Oil Set',
    image: '/images/product-oils.svg',
    description: 'A calming blend of professional oils for Swedish, deep tissue, and trigger point sessions.',
    price: 'GH₵ 220'
  },
  {
    name: 'Salon Styling Tools Case',
    image: '/images/product-tools.svg',
    description: 'Compact organizer for clips, combs, rollers, and the essentials for daily training.',
    price: 'GH₵ 195'
  },
  {
    name: 'Bridal Glow Palette',
    image: '/images/product-palette.svg',
    description: 'Elegant neutral tones curated for bridal looks, soft glam, and photo-ready finishes.',
    price: 'GH₵ 155'
  },
  {
    name: 'Beading Starter Box',
    image: '/images/product-beads.svg',
    description: 'A colourful starter set with curated beads and accessories for practical projects.',
    price: 'GH₵ 110'
  }
];
