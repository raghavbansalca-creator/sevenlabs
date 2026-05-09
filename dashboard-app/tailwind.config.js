/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,ts,jsx,tsx}'],
  theme: {
    extend: {
      colors: {
        frappe: {
          blue: '#2490EF',
          dark: '#1B1B1D',
          gray: '#8D99A6',
          light: '#F7FAFC',
        },
      },
    },
  },
  plugins: [],
}
