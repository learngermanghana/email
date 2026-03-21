import { NextResponse } from 'next/server';
import { FirestoreSaveError, saveRegistration } from '@/lib/server/firestore';

type RegistrationPayload = {
  fullName?: string;
  phone?: string;
  email?: string;
  course?: string;
  startMonth?: string;
  message?: string;
};

function validate(payload: RegistrationPayload) {
  return Boolean(payload.fullName && payload.phone && payload.email && payload.course && payload.startMonth);
}

export async function POST(request: Request) {
  try {
    const payload = (await request.json()) as RegistrationPayload;

    if (!validate(payload)) {
      return NextResponse.json({ error: 'Missing required fields.' }, { status: 400 });
    }

    await saveRegistration({
      fullName: payload.fullName!,
      phone: payload.phone!,
      email: payload.email!,
      course: payload.course!,
      startMonth: payload.startMonth!,
      message: payload.message || '',
      submittedAtIso: new Date().toISOString()
    });

    return NextResponse.json({ ok: true });
  } catch (error) {
    console.error('Registration save failed', error);
    if (error instanceof FirestoreSaveError) {
      return NextResponse.json({ error: 'Could not save registration at the moment.', reason: error.reason }, { status: error.status });
    }

    return NextResponse.json({ error: 'Could not save registration at the moment.', reason: 'unexpected_error' }, { status: 500 });
  }
}
