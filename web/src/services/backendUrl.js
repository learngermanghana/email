const DEFAULT_BACKEND_URL = process.env.REACT_APP_BACKEND_URL || "http://localhost:8000";

const DEFAULT_SPEAKING_API_URL =
  process.env.REACT_APP_SPEAKING_API_URL || DEFAULT_BACKEND_URL;

export const getBackendUrl = () => process.env.REACT_APP_BACKEND_URL || DEFAULT_BACKEND_URL;

export const getSpeakingApiUrl = () =>
  process.env.REACT_APP_SPEAKING_API_URL || DEFAULT_SPEAKING_API_URL;

export { DEFAULT_BACKEND_URL, DEFAULT_SPEAKING_API_URL };
