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
          bg:       "#080c14",   // sayfa arka plan — en koyu
          surface:  "#0f1520",   // kart arka plan
          raised:   "#161e2e",   // kart içi yükseltilmiş alan
          border:   "#1e2d42",   // ince sınır
          muted:    "#2d3f56",   // muted border / placeholder
          text:     "#e2e8f0",   // ana metin
          dim:      "#8899aa",   // ikincil metin
          faint:    "#4a5d72",   // en soluk metin
          blue:     "#60a5fa",   // vurgu
          teal:     "#2dd4bf",   // ikincil vurgu
        },
      },
      fontFamily: {
        sans: ["Inter", "system-ui", "sans-serif"],
        mono: ["JetBrains Mono", "Fira Code", "Consolas", "monospace"],
      },
      fontSize: {
        "2xs": ["0.65rem", { lineHeight: "1rem" }],
      },
      boxShadow: {
        "card": "0 1px 3px rgba(0,0,0,0.4), 0 0 0 1px rgba(255,255,255,0.03)",
        "glow-green":  "0 0 20px rgba(16,185,129,0.15)",
        "glow-amber":  "0 0 20px rgba(245,158,11,0.15)",
        "glow-orange": "0 0 20px rgba(249,115,22,0.12)",
        "glow-red":    "0 0 20px rgba(239,68,68,0.15)",
      },
    },
  },
  plugins: [],
};

export default config;
