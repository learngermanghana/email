import { createSign } from 'node:crypto';

type RegistrationPayload = {
  fullName: string;
  phone: string;
  email: string;
  course: string;
  startMonth: string;
  message: string;
  submittedAtIso: string;
};

type AccessTokenResponse = {
  access_token: string;
};

export class FirestoreSaveError extends Error {
  readonly status: number;
  readonly reason: string;

  constructor(message: string, status: number, reason: string) {
    super(message);
    this.name = 'FirestoreSaveError';
    this.status = status;
    this.reason = reason;
  }
}

const TOKEN_URL = 'https://oauth2.googleapis.com/token';
const FIRESTORE_SCOPE = 'https://www.googleapis.com/auth/datastore';

function requiredEnv(name: string) {
  const value = process.env[name];

  if (!value) {
    throw new FirestoreSaveError(`Missing environment variable: ${name}`, 503, 'config_missing');
  }

  return value;
}

function normalizePrivateKey(rawKey: string) {
  const unquotedKey =
    (rawKey.startsWith('"') && rawKey.endsWith('"')) || (rawKey.startsWith("'") && rawKey.endsWith("'"))
      ? rawKey.slice(1, -1)
      : rawKey;

  return unquotedKey.replace(/\\n/g, '\n');
}

function base64url(input: string) {
  return Buffer.from(input)
    .toString('base64')
    .replace(/=/g, '')
    .replace(/\+/g, '-')
    .replace(/\//g, '_');
}

function signJwt(unsignedToken: string, privateKey: string) {
  const signer = createSign('RSA-SHA256');
  signer.update(unsignedToken);
  signer.end();
  return signer.sign(privateKey, 'base64url');
}

async function getAccessToken() {
  const clientEmail = requiredEnv('FIREBASE_CLIENT_EMAIL');
  const privateKey = normalizePrivateKey(requiredEnv('FIREBASE_PRIVATE_KEY'));
  const issuedAt = Math.floor(Date.now() / 1000);

  const header = base64url(JSON.stringify({ alg: 'RS256', typ: 'JWT' }));
  const payload = base64url(
    JSON.stringify({
      iss: clientEmail,
      scope: FIRESTORE_SCOPE,
      aud: TOKEN_URL,
      iat: issuedAt,
      exp: issuedAt + 3600
    })
  );
  const unsignedToken = `${header}.${payload}`;
  const signature = signJwt(unsignedToken, privateKey);
  const assertion = `${unsignedToken}.${signature}`;

  const tokenResponse = await fetch(TOKEN_URL, {
    method: 'POST',
    headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
    body: new URLSearchParams({
      grant_type: 'urn:ietf:params:oauth:grant-type:jwt-bearer',
      assertion
    })
  });

  if (!tokenResponse.ok) {
    const errorText = await tokenResponse.text();
    throw new FirestoreSaveError(`Token request failed (${tokenResponse.status}): ${errorText}`, 502, 'token_request_failed');
  }

  const tokenData = (await tokenResponse.json()) as AccessTokenResponse;
  return tokenData.access_token;
}

export async function saveRegistration(payload: RegistrationPayload) {
  const projectId = requiredEnv('FIREBASE_PROJECT_ID');
  const accessToken = await getAccessToken();

  const response = await fetch(
    `https://firestore.googleapis.com/v1/projects/${projectId}/databases/(default)/documents/registrations`,
    {
      method: 'POST',
      headers: {
        Authorization: `Bearer ${accessToken}`,
        'Content-Type': 'application/json'
      },
      body: JSON.stringify({
        fields: {
          fullName: { stringValue: payload.fullName },
          phone: { stringValue: payload.phone },
          email: { stringValue: payload.email },
          course: { stringValue: payload.course },
          startMonth: { stringValue: payload.startMonth },
          message: { stringValue: payload.message },
          submittedAtIso: { stringValue: payload.submittedAtIso }
        }
      })
    }
  );

  if (!response.ok) {
    const errorText = await response.text();
    throw new FirestoreSaveError(
      `Firestore request failed (${response.status}): ${errorText}`,
      502,
      'firestore_write_failed'
    );
  }
}
