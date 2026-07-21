/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        cream: {
          DEFAULT: '#262624', // page background (dark warm charcoal)
          100: '#30302E',     // subtle tint / hover bg
        },
        surface: {
          DEFAULT: '#30302E', // card background
        },
        ink: {
          DEFAULT: '#E8E6DC',
          muted: '#ACA99F',
          faint: '#6B6963',
        },
        accent: {
          DEFAULT: '#E0825A',
          hover: '#EDA37E',
          tint: '#40291F',
          text: '#F0997B',
        },
        border: {
          DEFAULT: '#3C3B37',
          strong: '#4A4943',
        },
      },
      fontFamily: {
        sans: ['-apple-system', 'BlinkMacSystemFont', 'Segoe UI', 'Roboto', 'Helvetica Neue', 'sans-serif'],
        serif: ['"Source Serif 4"', 'Georgia', 'ui-serif', 'serif'],
      },
      borderRadius: {
        card: '12px',
      },
      boxShadow: {
        none: 'none',
      },
    },
  },
  plugins: [],
}
