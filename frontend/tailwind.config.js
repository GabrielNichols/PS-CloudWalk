/** @type {import('tailwindcss').Config} */
module.exports = {
  content: [
    "./src/**/*.{js,jsx,ts,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        'chatgpt-gray': '#202123',
        'chatgpt-dark': '#343541',
        'chatgpt-light': '#444654',
      }
    },
  },
  plugins: [],
}
