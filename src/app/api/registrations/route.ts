import { NextResponse } from 'next/server';
import { FirestoreSaveError, saveRegistration } from '@/lib/server/firestore';
import { PaymentError, verifyPayment } from '@/lib/server/payments';

type RegistrationPayload = {
  paymentReference?: string;
};

function validate(payload: RegistrationPayload) {
  return Boolean(payload.paymentReference);
}

export async function POST(request: Request) {
  try {
    const payload = (await request.json()) as RegistrationPayload;

    if (!validate(payload)) {
      return NextResponse.json({ error: 'Missing required fields.' }, { status: 400 });
    }

    const payment = await verifyPayment(payload.paymentReference!);

    await saveRegistration({
      paymentReference: payment.reference,
      fullName: payment.metadata.fullName,
      phone: payment.metadata.phone,
      email: payment.metadata.email,
      course: payment.metadata.course,
      startMonth: payment.metadata.startMonth,
      message: payment.metadata.message || '',
      submittedAtIso: payment.paidAtIso
    });

    return NextResponse.json({ ok: true });
  } catch (error) {
    console.error('Registration save failed', error);
    if (error instanceof PaymentError) {
      return NextResponse.json({ error: 'Could not verify payment.', reason: error.reason }, { status: error.status });
    }

    if (error instanceof FirestoreSaveError) {
      return NextResponse.json({ error: 'Could not save registration at the moment.', reason: error.reason }, { status: error.status });
    }

    return NextResponse.json({ error: 'Could not save registration at the moment.', reason: 'unexpected_error' }, { status: 500 });
  }
}
