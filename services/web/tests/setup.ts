//genai: Sprint 6 follow-up — global Vitest setup.
//
// Adds `@testing-library/jest-dom` matchers (`toBeInTheDocument`, …) and
// cleans up the DOM between tests so module-level state doesn't bleed.
import '@testing-library/jest-dom/vitest'
import { cleanup } from '@testing-library/react'
import { afterEach } from 'vitest'

afterEach(() => {
  cleanup()
})
