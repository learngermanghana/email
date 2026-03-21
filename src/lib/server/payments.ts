export type RegistrationMetadata = {
  fullName: string;
  phone: string;
  email: string;
  course: string;
  startMonth: string;
  message: string;
};

function hasRequiredMetadata(metadata: RegistrationMetadata | undefined): metadata is RegistrationMetadata {
  if (!metadata) {
    return false;
  }

  return Boolean(metadata.fullName && metadata.phone && metadata.email && metadata.course && metadata.startMonth);
}

type InitializeResponse = {
  status: boolean;
  message: string;
  data?: {
    authorization_url: string;
    reference: string;
  };
};

type VerifyResponse = {
  status: boolean;
  message: string;
  data?: {
    reference?: string;
    status: string;
    paid_at?: string;
    metadata?: RegistrationMetadata;
  };
};

const PAYSTACK_BASE_URL = 'https://api.paystack.co';
const PAYSTACK_SECRET_KEY_ENV = 'PAYSTACK_SECRET_KEY';
const PAYSTACK_PUBLIC_KEY_ENV = 'NEXT_PUBLIC_PAYSTACK_PUBLIC_KEY';
const REGISTRATION_AMOUNT_KOBO_ENV = 'REGISTRATION_FEE_KOBO';
const DEFAULT_REGISTRATION_AMOUNT_KOBO = 500000;

export class PaymentError extends Error {
  readonly status: number;
  readonly reason: string;

  constructor(message: string, status: number, reason: string) {
    super(message);
    this.name = 'PaymentError';
    this.status = status;
    this.reason = reason;
  }
}

function getPaymentConfig() {
  const secretKey = process.env[PAYSTACK_SECRET_KEY_ENV];
  const publicKey = process.env[PAYSTACK_PUBLIC_KEY_ENV];
  const amountRaw = process.env[REGISTRATION_AMOUNT_KOBO_ENV];
  const amountKobo = Number(amountRaw || DEFAULT_REGISTRATION_AMOUNT_KOBO);

  if (!secretKey || !publicKey) {
    throw new PaymentError(
      `Missing payment configuration (${PAYSTACK_SECRET_KEY_ENV} or ${PAYSTACK_PUBLIC_KEY_ENV}).`,
      503,
      'payment_config_missing'
    );
  }

  if (!Number.isInteger(amountKobo) || amountKobo <= 0) {
    throw new PaymentError(
      `${REGISTRATION_AMOUNT_KOBO_ENV} must be a positive integer.`,
      503,
      'payment_config_invalid'
    );
  }

  return { secretKey, amountKobo };
}

export async function initializeRegistrationPayment(metadata: RegistrationMetadata, callbackUrl: string) {
  const config = getPaymentConfig();

  const response = await fetch(`${PAYSTACK_BASE_URL}/transaction/initialize`, {
    method: 'POST',
    headers: {
      Authorization: `Bearer ${config.secretKey}`,
      'Content-Type': 'application/json'
    },
    body: JSON.stringify({
      email: metadata.email,
      amount: config.amountKobo,
      callback_url: callbackUrl,
      metadata
    })
  });

  const result = (await response.json().catch(() => null)) as InitializeResponse | null;

  if (!response.ok || !result?.status || !result.data?.authorization_url || !result.data.reference) {
    throw new PaymentError(
      `Payment initialization failed (${response.status}): ${result?.message || 'Unknown error'}`,
      502,
      'payment_initialize_failed'
    );
  }

  return {
    authorizationUrl: result.data.authorization_url,
    reference: result.data.reference
  };
}

export async function verifyPayment(reference: string) {
  const config = getPaymentConfig();

  const response = await fetch(`${PAYSTACK_BASE_URL}/transaction/verify/${encodeURIComponent(reference)}`, {
    headers: {
      Authorization: `Bearer ${config.secretKey}`
    }
  });

  const result = (await response.json().catch(() => null)) as VerifyResponse | null;

  if (!response.ok || !result?.status || !result.data) {
    throw new PaymentError(
      `Payment verification failed (${response.status}): ${result?.message || 'Unknown error'}`,
      502,
      'payment_verify_failed'
    );
  }

  if (result.data.status !== 'success') {
    throw new PaymentError('Payment was not successful.', 402, 'payment_not_successful');
  }

  if (!hasRequiredMetadata(result.data.metadata)) {
    throw new PaymentError('Payment metadata is missing.', 400, 'payment_metadata_missing');
  }

  const verifiedReference = result.data.reference || reference;

  return {
    reference: verifiedReference,
    metadata: result.data.metadata,
    paidAtIso: result.data.paid_at || new Date().toISOString()
  };
}
