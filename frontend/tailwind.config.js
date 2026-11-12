/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,jsx}'],
  theme: {
    extend: {
      colors: {
        brand: {
          50: '#eff5ff',
          100: '#dbe8ff',
          200: '#bfd6ff',
          300: '#93baff',
          400: '#5f93ff',
          500: '#3b76f6',
          600: '#2559e8',
          700: '#1d47c9',
          800: '#1d3da1',
          900: '#0d1b4b',
          950: '#08122f',
        },
        ink: {
          50: '#f6f7fb',
          100: '#eceef5',
          200: '#d9dce8',
          300: '#b8bed1',
          400: '#8b94ae',
          500: '#6b748f',
          600: '#555d76',
          700: '#434a60',
          800: '#2c3145',
          900: '#171b2c',
        },
        violet: {
          500: '#7c5cfc',
          600: '#6b46f0',
        },
        mint: {
          500: '#12b981',
          600: '#0e9f6e',
        },
      },
      fontFamily: {
        sans: [
          'Inter',
          'ui-sans-serif',
          'system-ui',
          '-apple-system',
          'Segoe UI',
          'Roboto',
          'Helvetica Neue',
          'Arial',
          'sans-serif',
        ],
      },
      boxShadow: {
        card: '0 1px 2px rgba(16, 24, 40, 0.04), 0 8px 24px -12px rgba(16, 24, 40, 0.12)',
        lift: '0 12px 32px -12px rgba(13, 27, 75, 0.28)',
      },
      borderRadius: {
        '2xl': '1.1rem',
        '3xl': '1.5rem',
      },
      keyframes: {
        'fade-up': {
          '0%': { opacity: '0', transform: 'translateY(8px)' },
          '100%': { opacity: '1', transform: 'translateY(0)' },
        },
      },
      animation: {
        'fade-up': 'fade-up 0.35s ease-out both',
      },
    },
  },
  plugins: [],
}
