import { NextResponse } from 'next/server';
import { PaymentError, initializeRegistrationPayment } from '@/lib/server/payments';

type PaymentInitPayload = {
  fullName?: string;
  phone?: string;
  email?: string;
  course?: string;
  startMonth?: string;
  message?: string;
};

function validate(payload: PaymentInitPayload) {
  return Boolean(payload.fullName && payload.phone && payload.email && payload.course && payload.startMonth);
}

export async function POST(request: Request) {
  try {
    const payload = (await request.json()) as PaymentInitPayload;

    if (!validate(payload)) {
      return NextResponse.json({ error: 'Missing required fields.' }, { status: 400 });
    }

    const origin = new URL(request.url).origin;
    const callbackUrl = `${origin}/register`;

    const initialized = await initializeRegistrationPayment(
      {
        fullName: payload.fullName!,
        phone: payload.phone!,
        email: payload.email!,
        course: payload.course!,
        startMonth: payload.startMonth!,
        message: payload.message || ''
      },
      callbackUrl
    );

    return NextResponse.json({ ok: true, ...initialized });
  } catch (error) {
    console.error('Payment initialization failed', error);

    if (error instanceof PaymentError) {
      return NextResponse.json({ error: 'Could not start payment.', reason: error.reason }, { status: error.status });
    }

    return NextResponse.json({ error: 'Could not start payment.', reason: 'unexpected_error' }, { status: 500 });
  }
}
