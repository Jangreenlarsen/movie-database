// Feature #103 — kører før hver testfil (se vite.config.js' test.setupFiles).
import "@testing-library/jest-dom/vitest";
import { cleanup } from "@testing-library/react";
import { afterEach, vi } from "vitest";

// React Testing Library rydder ikke selv op når `globals: true` bruges uden
// dens egen auto-cleanup — uden dette ville komponenter fra en test blive
// stående i DOM'en og forstyrre den næste.
afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
});
