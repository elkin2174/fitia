import "@testing-library/jest-dom/vitest";
import { cleanup } from "@testing-library/react";
import { afterAll, afterEach, beforeAll } from "vitest";
import { setAuthListener } from "../shared/api/client";
import { server } from "./server";

beforeAll(() => server.listen({ onUnhandledFrame: "error" }));
afterEach(() => {
  cleanup();
  server.resetHandlers();
  setAuthListener(null);
});
afterAll(() => server.close());

// jsdom no implementa scrollTo.
window.scrollTo = () => {};
