import type { Config } from 'tailwindcss'
import { heroui } from '@heroui/theme'

const config: Config = {
  content: [
    './index.html',
    './src/**/*.{js,ts,jsx,tsx}',
    './node_modules/@heroui/theme/dist/components/**/*.{js,ts,jsx,tsx}'
  ],
  darkMode: 'class', // 关键：和HTML的class属性对齐
  theme: {
    extend: {},
  },
  plugins: [heroui()],
}

export default config