module.exports = {
  content: [
    "./src/**/*.{html,js,jsx,ts,tsx}", // Scans all files in the src folder, including subdirectories
    "./public/**/*.html",               // Scans all HTML files in the public folder
    "./*.{html,js}",                     // Scans root-level HTML and JS files
  ],
  theme: {
    extend: {
      colors: {
        primary: '#4B5094',
        secondary: '#24ACD1'
      }
    },
  },
  plugins: [],
};
