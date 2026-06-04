/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        execution: {
          bg: 'var(--execution-bg)',
          surface: 'var(--execution-surface)',
          elevated: 'var(--execution-elevated)',
          primary: 'var(--execution-primary)',
          primaryDark: 'var(--execution-primary-dark)',
          violet: 'var(--execution-secondary)',
          signal: 'var(--execution-success)',
          border: 'var(--execution-border)',
        },
      },
      fontFamily: {
        sans: ['Manrope', 'ui-sans-serif', 'system-ui', 'sans-serif'],
        display: ['Sora', 'Manrope', 'ui-sans-serif', 'system-ui', 'sans-serif'],
        mono: ['JetBrains Mono', 'ui-monospace', 'SFMono-Regular', 'monospace'],
      },
    },
  },
  plugins: [],
}
