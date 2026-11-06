/**
 * Data access for Client Components. Import `api` from here; never call fetch directly.
 */
import { browserTransport } from "@/lib/api/browser-transport";
import type { MentorBridgeApi } from "@/lib/api/contract";
import { createLiveAuthApi, createLiveDataApi } from "@/lib/api/live";

export const api: MentorBridgeApi = {
  ...createLiveDataApi(browserTransport),
  auth: createLiveAuthApi(browserTransport),
};
