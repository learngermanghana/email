export const homepageImages = {
  hero: {
    src: '/uploads/homepage/WhatsApp Image 2026-03-21 at 18.01.12.jpeg',
    alt: 'Students training in a beauty classroom'
  },
  about: {
    src: '/uploads/homepage/WhatsApp Image 2026-03-21 at 18.01.13.jpeg',
    alt: 'Beauty school workstation and practical setup'
  },
  highlights: [
    {
      title: 'Bridal beauty looks',
      src: '/uploads/homepage/WhatsApp Image 2026-03-21 at 18.01.13 (1).jpeg',
      alt: 'Bridal make-up finish'
    },
    {
      title: 'Facial practicals',
      src: '/uploads/homepage/WhatsApp Image 2026-03-21 at 18.01.12 (2).jpeg',
      alt: 'Facial practical session'
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
