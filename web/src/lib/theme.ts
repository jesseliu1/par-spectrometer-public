/** Design tokens for code that cannot use CSS (ECharts options): values are read from tokens.css, never typed here. */

export function token(name: string, root: Element = document.documentElement): string {
  return getComputedStyle(root).getPropertyValue(name).trim();
}

export function tokenNumber(name: string, root?: Element): number {
  return Number.parseFloat(token(name, root));
}
