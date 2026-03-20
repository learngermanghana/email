import type { Config } from 'tailwindcss';

export default {
  content: ['./src/**/*.{js,ts,jsx,tsx,mdx}'],
  theme: {
    extend: {
      colors: {
        blush: '#f7d7df',
        rose: '#e9b7c3',
        nude: '#f3ece7',
        charcoal: '#2b2830',
        gold: '#c8a66a',
        cream: '#fffaf8'
      },
      backgroundImage: {
        'hero-glow': 'radial-gradient(circle at top, rgba(247,215,223,0.75), transparent 45%), linear-gradient(135deg, rgba(255,255,255,0.98), rgba(243,236,231,0.88))',
        'section-glow': 'linear-gradient(180deg, rgba(255,250,248,0.85), rgba(255,255,255,1))'
      },
      boxShadow: {
        soft: '0 20px 50px rgba(43, 40, 48, 0.08)',
        card: '0 10px 30px rgba(43, 40, 48, 0.08)'
      },
      borderRadius: {
        '4xl': '2rem'
      }
    }
  },
  plugins: []
} satisfies Config;
