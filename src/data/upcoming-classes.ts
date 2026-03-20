export type UpcomingClass = {
  id: string;
  name: string;
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
    startDate: '12 April 2026',
    duration: '6 months',
    schedule: 'Weekday • Morning',
    slots: 'Limited slots',
    category: 'Full Programs'
  },
  {
    id: 'hairdressing-april',
    name: 'Hairdressing',
    startDate: '20 April 2026',
    duration: '9 months',
    schedule: 'Weekday • Afternoon',
    slots: 'Few spaces left',
    category: 'Full Programs'
  },
  {
    id: 'massage-therapy-may',
    name: 'Massage Therapy',
    startDate: '5 May 2026',
    duration: '3 months',
    schedule: 'Weekend • Morning',
    slots: 'Limited slots',
    category: 'Full Programs'
  },
  {
    id: 'millinery-april',
    name: 'Millinery',
    startDate: '15 April 2026',
    duration: '6 weeks',
    schedule: 'Weekend • Afternoon',
    slots: 'Open for reservations',
    category: 'Short Courses'
  },
  {
    id: 'beading-april',
    name: 'Beading',
    startDate: '22 April 2026',
    duration: '4 weeks',
    schedule: 'Weekday • Afternoon',
    slots: 'Limited slots',
    category: 'Short Courses'
  },
  {
    id: 'grooming-monthly',
    name: 'Personal Grooming & Corporate Grooming',
    startDate: 'Runs this month',
    duration: '3 days',
    schedule: 'Weekend • Intensive',
    slots: 'Reserve early',
    category: 'Short Courses'
  }
];
