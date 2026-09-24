import type { Config } from "tailwindcss";

const config: Config = {
  content: ["./app/**/*.{ts,tsx}", "./components/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        brand: { 50: "#eff6ff", 100: "#dbeafe", 200: "#bfdbfe", 500: "#2a78d6", 600: "#1d4ed8", 700: "#1e40af", 900: "#1e3a8a" },
        sim: { 500: "#1baf7a", 700: "#0f7a54" },
        ink: { DEFAULT: "#0b0b0b", 2: "#52514e", muted: "#898781" },
      },
      fontFamily: { sans: ["var(--font-sans)", "system-ui", "sans-serif"] },
    },
  },
  plugins: [],
};
export default config;
