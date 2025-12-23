import { getBackendUrl } from "./backendUrl";

const backendUrl = getBackendUrl();

const buildUrl = (relativePath) => `${backendUrl}/${relativePath.replace(/^\/+/, "")}`;

export const callAI = async (relativePath, body, init = {}) => {
  const response = await fetch(buildUrl(relativePath), {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      ...(init.headers ?? {}),
    },
    body: JSON.stringify(body),
    ...init,
  });

  if (!response.ok) {
    const message = await response.text();
    throw new Error(`AI request failed (${response.status}): ${message}`);
  }

  return response.json();
};

export default { callAI };
