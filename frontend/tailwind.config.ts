import type { Config } from 'tailwindcss'
import defaultTheme from 'tailwindcss/defaultTheme'

export default <Config>{
  content: [
    './pages/**/*.{js,ts,jsx,tsx}',
    './components/**/*.{js,ts,jsx,tsx}',
    './app/**/*.{js,ts,jsx,tsx}',
  ],
  theme: {
    extend: {
      colors: {
        background: 'hsl(var(--background) / <alpha-value>)',
        foreground: 'hsl(var(--foreground) / <alpha-value>)',
        card: 'hsl(var(--card) / <alpha-value>)',
        "card-foreground": 'hsl(var(--card-foreground) / <alpha-value>)',
        popover: 'hsl(var(--popover) / <alpha-value>)',
        "popover-foreground": 'hsl(var(--popover-foreground) / <alpha-value>)',
        primary: 'hsl(210, 55%, 45%)',
        "primary-foreground": 'hsl(var(--primary-foreground) / <alpha-value>)',
        secondary: 'hsl(340, 70%, 55%)',
        "secondary-foreground": 'hsl(var(--secondary-foreground) / <alpha-value>)',
        success: 'hsl(140, 60%, 45%)',
        warning: 'hsl(30, 80%, 50%)',
        error: 'hsl(0, 80%, 45%)',
        muted: 'hsl(var(--muted) / <alpha-value>)',
        "muted-foreground": 'hsl(var(--muted-foreground) / <alpha-value>)',
        accent: 'hsl(var(--accent) / <alpha-value>)',
        "accent-foreground": 'hsl(var(--accent-foreground) / <alpha-value>)',
        destructive: 'hsl(var(--destructive) / <alpha-value>)',
        "destructive-foreground": 'hsl(var(--destructive-foreground) / <alpha-value>)',
        border: 'hsl(var(--border) / <alpha-value>)',
        input: 'hsl(var(--input) / <alpha-value>)',
        ring: 'hsl(var(--ring) / <alpha-value>)',
      },
      borderRadius: {
        lg: 'var(--radius)',
        md: 'calc(var(--radius) - 2px)',
        sm: 'calc(var(--radius) - 4px)',
      },
      fontFamily: {
        sans: ['Inter', ...defaultTheme.fontFamily.sans],
      },
    },
  },
  plugins: [],
}
