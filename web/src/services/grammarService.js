import { callAI } from "./aiClient";
import { getBackendUrl } from "./backendUrl";

const backendUrl = getBackendUrl();

export const askGrammar = (payload) => callAI("/grammar/ask", payload);

export { backendUrl };
