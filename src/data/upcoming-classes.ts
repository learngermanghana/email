export type UpcomingClass = {
  id: string;
  name: string;
  image: string;
  imageAlt: string;
  startDate: string;
  duration: string;
  schedule: string;
  slots: string;
  category: 'Full Programs' | 'Short Courses';
};

export const upcomingClasses: UpcomingClass[] = [
  {
    id: 'beauty-therapy-april',
    name: 'Beauty Therapy',
    image: '/uploads/courses/WhatsApp Image 2026-03-21 at 17.57.49 (1).jpeg',
    imageAlt: 'Beauty therapy practical training in session',
    startDate: '12 April 2026',
    duration: '6 months',
    schedule: 'Weekday • Morning',
    slots: 'Limited slots',
    category: 'Full Programs'
  },
  {
    id: 'hairdressing-april',
    name: 'Hairdressing',
    image: '/uploads/homepage/hairdressing.jpeg',
    imageAlt: 'Hairdressing class with mannequin practice',
    startDate: '20 April 2026',
    duration: '9 months',
    schedule: 'Weekday • Afternoon',
    slots: 'Few spaces left',
    category: 'Full Programs'
  },
  {
    id: 'massage-therapy-may',
    name: 'Massage Therapy',
    image: '/uploads/homepage/MAssage therepy.jpeg',
    imageAlt: 'Massage therapy demonstration during class',
    startDate: '5 May 2026',
    duration: '3 months',
    schedule: 'Weekend • Morning',
    slots: 'Limited slots',
    category: 'Full Programs'
  },
  {
    id: 'millinery-april',
    name: 'Millinery',
    image: '/uploads/courses/Millinery.jpeg',
    imageAlt: 'Millinery students working on hat design',
    startDate: '15 April 2026',
    duration: '6 weeks',
    schedule: 'Weekend • Afternoon',
    slots: 'Open for reservations',
    category: 'Short Courses'
  },
  {
    id: 'beading-april',
    name: 'Beading',
    image: '/uploads/courses/Beading7.jpeg',
    imageAlt: 'Beading class with handcrafted accessories',
    startDate: '22 April 2026',
    duration: '4 weeks',
    schedule: 'Weekday • Afternoon',
    slots: 'Limited slots',
    category: 'Short Courses'
  },
  {
    id: 'grooming-monthly',
    name: 'Personal Grooming & Corporate Grooming',
    image: '/uploads/courses/Personal Grooming .jpeg',
    imageAlt: 'Personal grooming workshop led by an instructor',
    startDate: 'Runs this month',
    duration: '3 days',
    schedule: 'Weekend • Intensive',
    slots: 'Reserve early',
    category: 'Short Courses'
  }
];
