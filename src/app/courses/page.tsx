import type { Metadata } from 'next';
import { CourseCard } from '@/components/course-card';
import { SectionHeading } from '@/components/section-heading';
import { courses } from '@/data/courses';

export const metadata: Metadata = {
  title: 'Courses',
  description: 'Explore beauty therapy, hairdressing, massage therapy, millinery, beading, and grooming courses at Make Up & More School of Cosmetology in Tema.'
};

export default function CoursesPage() {
  return (
    <div className="section-shell py-16 sm:py-20">
      <SectionHeading
        eyebrow="Courses"
        title="Explore professional beauty training designed for beginners and aspiring experts."
        description="Choose from full cosmetology programs and flexible short courses created for beauty entrepreneurs, salon professionals, and learners who want practical, elegant training in Tema."
      />
      <div className="mt-10 grid gap-6 xl:grid-cols-2">
        {courses.map((course) => (
          <CourseCard key={course.slug} course={course} />
        ))}
      </div>
    </div>
  );
}
