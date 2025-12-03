import type { Config } from "tailwindcss";
import animatePlugin from "tailwindcss-animate";

const config: Config = {
  content: [
    "./src/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  darkMode: "class",
  theme: {
    extend: {
      fontFamily: {
        sans: ["JetBrains Mono", "monospace"],
        display: ["IBM Plex Sans", "sans-serif"],
      },
      colors: {
        background: "var(--background)",
        foreground: "var(--foreground)",
        card: "var(--card)",
        "card-foreground": "var(--card-foreground)",
        border: "var(--border)",
        input: "var(--input)",
        ring: "var(--ring)",
        muted: "var(--muted)",
        "muted-foreground": "var(--muted-foreground)",
        accent: "var(--accent)",
        "accent-foreground": "var(--accent-foreground)",
        // Raven-inspired dark theme
        raven: {
          50: "#f7f7f8",
          100: "#e3e4e6",
          200: "#c7c9cd",
          300: "#a4a7ae",
          400: "#81858e",
          500: "#666a73",
          600: "#51555c",
          700: "#42454b",
          800: "#38393f",
          900: "#1a1b1e",
          950: "#0d0e10",
        },
        // Sterling silver - 925+ purity
        silver: {
          50: "#fafafa",
          100: "#f4f4f5",
          200: "#e4e4e7",
          300: "#d4d4d8",
          400: "#a1a1aa",
          500: "#71717a",
          600: "#52525b",
          700: "#3f3f46",
          800: "#27272a",
          900: "#18181b",
        },
        // Odin's eye - now sterling silver accent
        odin: {
          50: "#fafafa",
          100: "#f4f4f5",
          200: "#e4e4e7",
          300: "#d4d4d8",
          400: "#a8aeb5",
          500: "#9a9ea6",
          600: "#6a7078",
          700: "#52525b",
          800: "#3f3f46",
          900: "#27272a",
        },
        // Huginn (thought) - cyan for real-time
        huginn: {
          400: "#22d3ee",
          500: "#06b6d4",
          600: "#0891b2",
        },
        // Muninn (memory) - purple for persistence
        muninn: {
          400: "#c084fc",
          500: "#a855f7",
          600: "#9333ea",
        },
        // Status colors
        healthy: "#10b981",
        degraded: "#f59e0b",
        unhealthy: "#ef4444",
      },
      backgroundImage: {
        "gradient-radial": "radial-gradient(var(--tw-gradient-stops))",
        "gradient-norse": "linear-gradient(135deg, #0d0e10 0%, #1a1b1e 50%, #0d0e10 100%)",
        "glow-silver": "radial-gradient(ellipse at center, rgba(168, 174, 181, 0.12) 0%, transparent 70%)",
      },
      animation: {
        "pulse-slow": "pulse 3s cubic-bezier(0.4, 0, 0.6, 1) infinite",
        "float": "float 6s ease-in-out infinite",
        "glow": "glow 2s ease-in-out infinite alternate",
      },
      keyframes: {
        float: {
          "0%, 100%": { transform: "translateY(0)" },
          "50%": { transform: "translateY(-10px)" },
        },
        glow: {
          "0%": { boxShadow: "0 0 5px rgba(168, 174, 181, 0.2)" },
          "100%": { boxShadow: "0 0 20px rgba(168, 174, 181, 0.35)" },
        },
      },
    },
  },
  plugins: [animatePlugin],
};

export default config;

