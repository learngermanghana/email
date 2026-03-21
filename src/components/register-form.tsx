'use client';

import type { FormEvent, ReactNode } from 'react';
import { useMemo, useState } from 'react';
import { courses } from '@/data/courses';

type FormState = {
  fullName: string;
  phone: string;
  email: string;
  course: string;
  startMonth: string;
  message: string;
};

const initialState: FormState = {
  fullName: '',
  phone: '',
  email: '',
  course: '',
  startMonth: '',
  message: ''
};

export function RegisterForm() {
  const [form, setForm] = useState<FormState>(initialState);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');
  const [isSubmitting, setIsSubmitting] = useState(false);

  const helperText = useMemo(
    () => 'Submitting this form securely saves your registration so our admissions team can follow up quickly.',
    []
  );

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();

    if (!form.fullName || !form.phone || !form.email || !form.course || !form.startMonth) {
      setError('Please complete all required fields before submitting.');
      setSuccess('');
      return;
    }
    setIsSubmitting(true);
    setError('');
    setSuccess('');

    try {
      const response = await fetch('/api/registrations', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json'
        },
        body: JSON.stringify(form)
      });

      if (!response.ok) {
        const payload = (await response.json().catch(() => null)) as { reason?: string } | null;
        const reason = payload?.reason ? ` (${payload.reason})` : '';
        throw new Error(`Registration save failed with status ${response.status}${reason}`);
      }

      setForm(initialState);
      setSuccess('Thanks! Your registration has been submitted successfully.');
    } catch (submissionError) {
      console.error(submissionError);
      setError('Could not submit your registration right now. Please try again in a moment.');
    } finally {
      setIsSubmitting(false);
    }
  }

  return (
    <form onSubmit={handleSubmit} className="rounded-[2rem] border border-black/5 bg-white p-8 shadow-soft sm:p-10">
      <div className="mb-8 rounded-3xl bg-nude/70 p-5 text-sm leading-7 text-charcoal/75">{helperText}</div>
      <div className="grid gap-5 md:grid-cols-2">
        <Field label="Full name" required>
          <input value={form.fullName} onChange={(event) => setForm({ ...form, fullName: event.target.value })} className="input" />
        </Field>
        <Field label="Phone number" required>
          <input value={form.phone} onChange={(event) => setForm({ ...form, phone: event.target.value })} className="input" />
        </Field>
        <Field label="Email address" required>
          <input type="email" value={form.email} onChange={(event) => setForm({ ...form, email: event.target.value })} className="input" />
        </Field>
        <Field label="Course interested in" required>
          <select value={form.course} onChange={(event) => setForm({ ...form, course: event.target.value })} className="input">
            <option value="">Select a course</option>
            {courses.map((course) => (
              <option key={course.slug} value={course.name}>{course.name}</option>
            ))}
          </select>
        </Field>
        <Field label="Preferred start month" required>
          <input value={form.startMonth} onChange={(event) => setForm({ ...form, startMonth: event.target.value })} placeholder="e.g. May 2026" className="input" />
        </Field>
        <Field label="Message">
          <input value={form.message} onChange={(event) => setForm({ ...form, message: event.target.value })} placeholder="Tell us about your goals or preferred schedule." className="input" />
        </Field>
      </div>
      {error ? <p className="mt-4 text-sm font-medium text-rose-700">{error}</p> : null}
      {success ? <p className="mt-4 text-sm font-medium text-emerald-700">{success}</p> : null}
      <button type="submit" disabled={isSubmitting} className="mt-8 inline-flex rounded-full bg-charcoal px-6 py-3 text-sm font-medium text-white transition hover:bg-charcoal/90 disabled:cursor-not-allowed disabled:opacity-70">
        {isSubmitting ? 'Submitting...' : 'Submit registration'}
      </button>
    </form>
  );
}

function Field({ label, required, children }: { label: string; required?: boolean; children: ReactNode }) {
  return (
    <label className="space-y-2 text-sm font-medium text-charcoal">
      <span>
        {label} {required ? <span className="text-gold">*</span> : null}
      </span>
      {children}
    </label>
  );
}
