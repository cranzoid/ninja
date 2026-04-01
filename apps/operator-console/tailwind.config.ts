import type { Config } from 'tailwindcss';

const config: Config = {
  content: [
    './src/pages/**/*.{js,ts,jsx,tsx,mdx}',
    './src/components/**/*.{js,ts,jsx,tsx,mdx}',
    './src/app/**/*.{js,ts,jsx,tsx,mdx}',
  ],
  theme: {
    extend: {
      colors: {
        console: {
          bg: '#0a0a0f',
          'bg-card': 'rgba(255,255,255,0.03)',
          'bg-hover': 'rgba(255,255,255,0.06)',
          border: 'rgba(255,255,255,0.06)',
          'border-active': 'rgba(255,255,255,0.12)',
          sidebar: '#0d0d14',
        },
        profit: '#22c55e',
        loss: '#ef4444',
        warning: '#f59e0b',
        info: '#3b82f6',
        regime: {
          green: '#22c55e',
          mixed: '#f59e0b',
          stressed: '#8b5cf6',
        },
      },
      fontFamily: {
        mono: ['JetBrains Mono', 'Fira Code', 'Menlo', 'monospace'],
        sans: ['IBM Plex Sans', 'Inter', 'system-ui', 'sans-serif'],
      },
      fontSize: {
        '2xs': '0.65rem',
      },
    },
  },
  plugins: [],
};

export default config;
