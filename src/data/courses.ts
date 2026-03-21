export type Course = {
  slug: string;
  name: string;
  duration: string;
  summary: string;
  category: 'Full Program' | 'Short Course';
  image: string;
  imageAlt: string;
  modules?: string[];
};

export const courses: Course[] = [
  {
    slug: 'beauty-therapy',
    name: 'Beauty Therapy',
    duration: '6 months',
    summary: 'Master spa-ready beauty services, advanced skin care, and polished make-up artistry.',
    category: 'Full Program',
    image: '/uploads/courses/beauty-therapy.svg',
    imageAlt: 'Beauty therapy practical session',
    modules: [
      'Anatomy & Physiology',
      'Nail Care (Pedicure & Manicure)',
      'Nail Extension',
      'Skin Care',
      'Facial Therapy',
      'Make-up Artistry'
    ]
  },
  {
    slug: 'hairdressing',
    name: 'Hairdressing',
    duration: '9 months',
    summary: 'Build salon confidence in styling, braiding, extensions, treatments, and foundational theory.',
    category: 'Full Program',
    image: '/uploads/courses/hairdressing.svg',
    imageAlt: 'Hairdressing braids practice',
    modules: [
      'Anatomy & Physiology',
      'Shampooing and Roller Setting',
      'Hairstyling',
      'Hair Extension',
      'Braids (2 Stem & 3 Stem Braids)',
      'Cornroll',
      'Basic Wig Caps',
      'Hair Treatment'
    ]
  },
  {
    slug: 'massage-therapy',
    name: 'Massage Therapy',
    duration: '3 months',
    summary: 'Train in therapeutic touch with industry-relevant massage techniques and client care.',
    category: 'Full Program',
    image: '/uploads/courses/massage-therapy.svg',
    imageAlt: 'Massage therapy facial training setup',
    modules: ['Deep tissue', 'Shiatsu', 'Swedish', 'Trigger point massage', 'Personalised massage therapy']
  },
  {
    slug: 'millinery',
    name: 'Millinery',
    duration: '6 weeks',
    summary: 'Learn premium fascinator and hat construction for modern fashion and occasion wear.',
    category: 'Short Course',
    image: '/uploads/courses/millinery.svg',
    imageAlt: 'Creative beauty styling image used for millinery course',
    modules: ['Fabric accessories', 'Fascinator', 'Hats', 'Hatinators']
  },
  {
    slug: 'beading',
    name: 'Beading',
    duration: '4 weeks',
    summary: 'Create sellable handcrafted accessories with practical beading techniques.',
    category: 'Short Course',
    image: '/uploads/courses/beading.svg',
    imageAlt: 'Beading starter kit materials',
    modules: ['Necklace', 'Bags', 'Slippers']
  },
  {
    slug: 'personal-grooming-corporate-grooming',
    name: 'Personal Grooming & Corporate Grooming',
    duration: '3 days',
    summary: 'A polished finishing course for confidence, etiquette, and image-ready presentation.',
    category: 'Short Course',
    image: '/uploads/courses/personal-grooming-corporate-grooming.svg',
    imageAlt: 'Elegant beauty finish for grooming course'
  },
  {
    slug: 'short-courses',
    name: 'Short Courses',
    duration: 'Variable duration',
    summary: 'Flexible beauty skill intensives created for busy professionals, beginners, and hobbyists.',
    category: 'Short Course',
    image: '/uploads/courses/short-courses.svg',
    imageAlt: 'Beauty classroom workstation for short courses'
  }
];
