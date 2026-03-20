export type Course = {
  slug: string;
  name: string;
  duration: string;
  summary: string;
  category: 'Full Program' | 'Short Course';
  modules?: string[];
};

export const courses: Course[] = [
  {
    slug: 'beauty-therapy',
    name: 'Beauty Therapy',
    duration: '6 months',
    summary: 'Master spa-ready beauty services, advanced skin care, and polished make-up artistry.',
    category: 'Full Program',
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
    modules: ['Deep tissue', 'Shiatsu', 'Swedish', 'Trigger point massage', 'Personalised massage therapy']
  },
  {
    slug: 'millinery',
    name: 'Millinery',
    duration: '6 weeks',
    summary: 'Learn premium fascinator and hat construction for modern fashion and occasion wear.',
    category: 'Short Course',
    modules: ['Fabric accessories', 'Fascinator', 'Hats', 'Hatinators']
  },
  {
    slug: 'beading',
    name: 'Beading',
    duration: '4 weeks',
    summary: 'Create sellable handcrafted accessories with practical beading techniques.',
    category: 'Short Course',
    modules: ['Necklace', 'Bags', 'Slippers']
  },
  {
    slug: 'personal-grooming-corporate-grooming',
    name: 'Personal Grooming & Corporate Grooming',
    duration: '3 days',
    summary: 'A polished finishing course for confidence, etiquette, and image-ready presentation.',
    category: 'Short Course'
  },
  {
    slug: 'short-courses',
    name: 'Short Courses',
    duration: 'Variable duration',
    summary: 'Flexible beauty skill intensives created for busy professionals, beginners, and hobbyists.',
    category: 'Short Course'
  }
];
