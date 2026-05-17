import type { Config } from "tailwindcss";

export default {
  darkMode: ["class"],
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      fontFamily: {
        sans: ["Inter", "ui-sans-serif", "system-ui", "Microsoft YaHei", "sans-serif"],
        mono: ["JetBrains Mono", "SFMono-Regular", "Consolas", "monospace"]
      },
      colors: {
        surface: {
          base: "#080b10",
          raised: "#0d121a",
          panel: "rgba(15, 23, 32, 0.72)"
        }
      },
      boxShadow: {
        glow: "0 0 0 1px rgba(103, 232, 249, 0.13), 0 16px 60px rgba(0, 0, 0, 0.38)",
        lift: "0 18px 70px rgba(0, 0, 0, 0.46)"
      },
      borderRadius: {
        panel: "8px"
      }
    }
  },
  plugins: []
} satisfies Config;

