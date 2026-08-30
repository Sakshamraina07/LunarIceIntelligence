// Tailwind v4 runs via the @tailwindcss/vite plugin (see vite.config.ts), so no
// PostCSS plugins are needed here. This empty config exists only to stop PostCSS
// from walking up and picking the repo-root Next.js config (which requires
// @tailwindcss/postcss, not installed in this frontend workspace).
export default {};
