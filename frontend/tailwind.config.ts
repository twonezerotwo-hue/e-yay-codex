import type { Config } from "tailwindcss";

const config: Config = {
  content: [
    "./app/**/*.{js,ts,jsx,tsx,mdx}",
    "./components/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  theme: {
    extend: {
      colors: {
        eyay: {
          bg:       "#0a0e17",
          surface:  "#111827",
          border:   "#1f2937",
          muted:    "#374151",
          text:     "#e5e7eb",
          dim:      "#9ca3af",
          accent:   "#3b82f6",
          green:    "#10b981",
          yellow:   "#f59e0b",
          orange:   "#f97316",
          red:      "#ef4444",
          blue:     "#60a5fa",
        },
      },
      fontFamily: {
        mono: ["JetBrains Mono", "Fira Code", "Consolas", "monospace"],
      },
    },
  },
  plugins: [],
};

export default config;
