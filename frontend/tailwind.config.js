/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      fontFamily: {
        outfit: ['Outfit', 'system-ui', 'sans-serif'],
        mono: ['JetBrains Mono', 'monospace'],
        display: ['Outfit', 'sans-serif'],
      },
      colors: {
        brand: {
          50: '#eff6ff',
          100: '#dbeafe',
          500: '#2f7de2',
          600: '#1e5bb8',
          700: '#174a94',
        },
        ink: {
          DEFAULT: '#0f172a',
          light: '#334155',
          muted: '#64748b',
        }
      },
      boxShadow: {
        'soft': '0 2px 10px rgba(15,23,42,0.06)',
        'card': '0 1px 3px rgba(15,23,42,0.08), 0 4px 12px rgba(15,23,42,0.04)',
        'elevated': '0 8px 30px rgba(15,23,42,0.12)',
      }
    },
  },
  plugins: [],
}
