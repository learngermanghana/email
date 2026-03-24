export const homepageImages = {
  hero: {
    src: '/uploads/homepage/WhatsApp Image 2026-03-21 at 18.01.12 (3).jpeg',
    alt: 'Students training in a beauty classroom'
  },
  about: {
    src: '/uploads/homepage/Personal grooming class 3.jpeg',
    alt: 'Students during a personal grooming practical class'
  },
  highlights: [
    {
      title: 'Personal grooming class',
      src: '/uploads/homepage/Personal grooming class.jpeg',
      alt: 'Students attending a personal grooming lesson'
    },
    {
      title: 'Corporate grooming practical',
      src: '/uploads/homepage/personal grooming class 2.jpeg',
      alt: 'Personal and corporate grooming practice session'
    }
  ],
  braids: [
    {
      title: 'Classic makeup practical',
      src: '/uploads/homepage/hairdressing braids 1.jpeg',
      alt: 'Student makeup practical look 1'
    },
    {
      title: 'Beauty practical session',
      src: '/uploads/homepage/hairdressing braids 2.jpeg',
      alt: 'Student makeup practical look 2'
    },
    {
      title: 'Focused product application',
      src: '/uploads/homepage/hairdressing braids 3.jpeg',
      alt: 'Student makeup practical look 3'
    },
    {
      title: 'Detailed classroom technique',
      src: '/uploads/homepage/hairdressing braids 4.jpeg',
      alt: 'Student makeup practical look 4'
    },
    {
      title: 'Salon-ready makeup result',
      src: '/uploads/homepage/hairdressing braids 5.jpeg',
      alt: 'Student makeup practical look 5'
    },
    {
      title: 'Makeup practical in progress',
      src: '/uploads/homepage/hairdressing braids 6.jpeg',
      alt: 'Student makeup practical look 6'
    },
    {
      title: 'Advanced makeup practice',
      src: '/uploads/homepage/hairdressig braids 7.jpeg',
      alt: 'Student makeup practical look 7'
    },
    {
      title: 'Detailed makeup finishing',
      src: '/uploads/homepage/hairdressing braids 8.jpeg',
      alt: 'Student makeup practical look 8'
    }
  ]
} as const;

export const uploadFolders = [
  {
    name: 'Homepage photos',
    folder: 'public/uploads/homepage',
    usage: 'Hero image, about section image, and extra home-page highlights.'
  },
  {
    name: 'Course photos',
    folder: 'public/uploads/courses',
    usage: 'One image per course card and course preview.'
  },
  {
    name: 'Product photos',
    folder: 'public/uploads/products',
    usage: 'Product cards on the products page and homepage preview.'
  },
  {
    name: 'Gallery photos',
    folder: 'public/uploads/gallery',
    usage: 'Full gallery items and homepage gallery preview.'
  }
] as const;

export const photoUploadSteps = [
  'Export your photo as JPG, PNG, or WebP and give it a simple descriptive name.',
  'Replace the matching file inside the correct public/uploads folder to keep the page linked automatically.',
  'If you add a brand-new image name, update the related file in src/data so the page points to the new path.',
  'Commit the new asset and deploy to publish it.'
] as const;
