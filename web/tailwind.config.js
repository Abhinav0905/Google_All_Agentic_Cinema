/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{js,jsx}"],
  theme: {
    extend: {
      colors: {
        bay: {
          950: "#090b10",
          900: "#0c0e14",
          850: "#12151d",
          800: "#181c27",
          700: "#232836",
          500: "#8b93a7",
          300: "#d5dae6",
          100: "#f4f6fb",
        },
        error: "#ef4444",
        warn: "#f59e0b",
        info: "#64748b",
        pass: "#10b981",
        accent: "#818cf8",
      },
      fontFamily: {
        sans: [
          "IBM Plex Sans",
          "Segoe UI",
          "Helvetica Neue",
          "Arial",
          "sans-serif",
        ],
        mono: ["IBM Plex Mono", "ui-monospace", "SFMono-Regular", "Menlo", "monospace"],
      },
    },
  },
  plugins: [],
};
