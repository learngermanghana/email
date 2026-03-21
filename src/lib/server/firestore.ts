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

type ServiceAccountConfig = {
  projectId: string;
  clientEmail: string;
  privateKey: string;
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
const SERVICE_ACCOUNT_JSON_ENV = 'FIREBASE_SERVICE_ACCOUNT_JSON';

const PROJECT_ID_ENV_NAMES = ['FIREBASE_PROJECT_ID', 'GOOGLE_CLOUD_PROJECT', 'GCLOUD_PROJECT', 'NEXT_PUBLIC_FIREBASE_PROJECT_ID'];
const CLIENT_EMAIL_ENV_NAMES = ['FIREBASE_CLIENT_EMAIL', 'FIREBASE_ADMIN_CLIENT_EMAIL', 'GOOGLE_CLIENT_EMAIL'];
const PRIVATE_KEY_ENV_NAMES = ['FIREBASE_PRIVATE_KEY', 'FIREBASE_ADMIN_PRIVATE_KEY', 'GOOGLE_PRIVATE_KEY'];

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

function getFirstDefinedValue(names: string[]) {
  for (const name of names) {
    const value = process.env[name];
    if (value) {
      return value;
    }
  }

  return '';
}

function parseServiceAccountJson(rawJson: string) {
  try {
    const parsed = JSON.parse(rawJson) as { project_id?: string; client_email?: string; private_key?: string };

    return {
      projectId: parsed.project_id || '',
      clientEmail: parsed.client_email || '',
      privateKey: parsed.private_key || ''
    };
  } catch {
    throw new FirestoreSaveError(
      `${SERVICE_ACCOUNT_JSON_ENV} is not valid JSON.`,
      503,
      'config_missing'
    );
  }
}

function getFirebaseConfig() {
  const serviceAccountJson = process.env[SERVICE_ACCOUNT_JSON_ENV];
  const fromJson = serviceAccountJson ? parseServiceAccountJson(serviceAccountJson) : null;

  const projectId = fromJson?.projectId || getFirstDefinedValue(PROJECT_ID_ENV_NAMES);
  const clientEmail = fromJson?.clientEmail || getFirstDefinedValue(CLIENT_EMAIL_ENV_NAMES);
  const privateKey = normalizePrivateKey(fromJson?.privateKey || getFirstDefinedValue(PRIVATE_KEY_ENV_NAMES));

  const missing: string[] = [];

  if (!projectId) {
    missing.push(`project id (${PROJECT_ID_ENV_NAMES.join(' | ')})`);
  }

  if (!clientEmail) {
    missing.push(
      `service account client email (${CLIENT_EMAIL_ENV_NAMES.join(' | ')})`
    );
  }

  if (!privateKey) {
    missing.push(`service account private key (${PRIVATE_KEY_ENV_NAMES.join(' | ')})`);
  }

  if (missing.length > 0) {
    throw new FirestoreSaveError(
      `Missing Firebase server configuration: ${missing.join(', ')}. You can also provide ${SERVICE_ACCOUNT_JSON_ENV}.`,
      503,
      'config_missing'
    );
  }

  return {
    projectId,
    clientEmail,
    privateKey
  } satisfies ServiceAccountConfig;
}

async function getAccessToken(config: ServiceAccountConfig) {
  const issuedAt = Math.floor(Date.now() / 1000);

  const header = base64url(JSON.stringify({ alg: 'RS256', typ: 'JWT' }));
  const payload = base64url(
    JSON.stringify({
      iss: config.clientEmail,
      scope: FIRESTORE_SCOPE,
      aud: TOKEN_URL,
      iat: issuedAt,
      exp: issuedAt + 3600
    })
  );
  const unsignedToken = `${header}.${payload}`;
  const signature = signJwt(unsignedToken, config.privateKey);
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
  const config = getFirebaseConfig();
  const accessToken = await getAccessToken(config);

  const response = await fetch(
    `https://firestore.googleapis.com/v1/projects/${config.projectId}/databases/(default)/documents/registrations`,
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
