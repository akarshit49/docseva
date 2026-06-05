//genai: Sprint 3 / WS-F — Tailwind config tuned to the §17 design system tokens.
import type { Config } from 'tailwindcss'

const config: Config = {
  content: [
    './app/**/*.{ts,tsx}',
    './components/**/*.{ts,tsx}',
    './hooks/**/*.{ts,tsx}',
    './lib/**/*.{ts,tsx}',
  ],
  theme: {
    container: {
      center: true,
      padding: '1rem',
      screens: {
        '2xl': '1200px',
      },
    },
    extend: {
      colors: {
        // Mirror the §17.2 palette so component code reads as intent, not raw indigo-600.
        brand: {
          DEFAULT: '#4f46e5', // indigo-600
          hover: '#4338ca', // indigo-700
          soft: '#eef2ff', // indigo-50
          fg: '#ffffff',
        },
        success: { DEFAULT: '#059669', soft: '#ecfdf5' },
        warning: { DEFAULT: '#f59e0b', soft: '#fffbeb' },
        danger: { DEFAULT: '#e11d48', soft: '#fff1f2' },
        ink: {
          900: '#0f172a',
          700: '#334155',
          500: '#64748b',
          300: '#cbd5e1',
          100: '#f1f5f9',
        },
      },
      fontFamily: {
        sans: ['Inter', 'IBM Plex Sans', 'ui-sans-serif', 'system-ui', 'sans-serif'],
      },
      boxShadow: {
        card: '0 1px 2px rgba(15, 23, 42, 0.06), 0 4px 12px rgba(15, 23, 42, 0.06)',
      },
      maxWidth: {
        wizard: '720px',
      },
      keyframes: {
        'fade-in': {
          '0%': { opacity: '0', transform: 'translateY(4px)' },
          '100%': { opacity: '1', transform: 'translateY(0)' },
        },
      },
      animation: {
        'fade-in': 'fade-in 200ms ease-out',
      },
    },
  },
  plugins: [],
}

export default config
