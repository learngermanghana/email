import { getBackendUrl, getSpeakingApiUrl } from "./backendUrl";

const backendUrl = getBackendUrl();
const speakingApiUrl = getSpeakingApiUrl() || backendUrl;

const postJson = async (url, body) => {
  const response = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });

  if (!response.ok) {
    const message = await response.text();
    throw new Error(`Request to ${url} failed (${response.status}): ${message}`);
  }

  return response.json();
};

export const markWriting = (payload) => postJson(`${backendUrl}/writing/mark`, payload);

export const generateWritingIdeas = (payload) =>
  postJson(`${backendUrl}/writing/ideas`, payload);

export const analyzeSpeaking = (payload) =>
  postJson(`${speakingApiUrl}/speaking/analyze`, payload);

export const analyzeSpeakingText = (payload) =>
  postJson(`${speakingApiUrl}/speaking/analyze-text`, payload);

export const fetchInteractionScore = (payload) =>
  postJson(`${speakingApiUrl}/speaking/interaction-score`, payload);

export { backendUrl, speakingApiUrl };
