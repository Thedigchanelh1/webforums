/** @type {import('tailwindcss').Config} */
export default {
  darkMode: 'class',
  content: ['./index.html', './src/**/*.{js,jsx}'],
  theme: {
    extend: {
      colors: {
        base: {
          DEFAULT: '#0A0C10',
          panel: '#14171D',
          raised: '#1B1F27',
          border: '#262B35',
        },
        ink: {
          primary: '#EDEFF3',
          muted: '#8B93A3',
          faint: '#565C6B',
        },
        accent: {
          DEFAULT: '#7C9EFF',
          soft: '#3B4A7A',
        },
        urgency: {
          high: '#F0465B',
          highSoft: '#3A1A22',
          medium: '#F5A623',
          mediumSoft: '#3A2E14',
          low: '#34D399',
          lowSoft: '#123529',
        },
      },
      fontFamily: {
        display: ['"Space Grotesk"', 'sans-serif'],
        body: ['"Inter"', 'sans-serif'],
        mono: ['"JetBrains Mono"', 'monospace'],
      },
      keyframes: {
        pulseDot: {
          '0%, 100%': { boxShadow: '0 0 0 0 rgba(240,70,91,0.55)' },
          '50%': { boxShadow: '0 0 0 6px rgba(240,70,91,0)' },
        },
        slideDown: {
          from: { opacity: 0, transform: 'translateY(-4px)' },
          to: { opacity: 1, transform: 'translateY(0)' },
        },
      },
      animation: {
        pulseDot: 'pulseDot 2s ease-in-out infinite',
        slideDown: 'slideDown 0.18s ease-out',
      },
    },
  },
  plugins: [],
}
