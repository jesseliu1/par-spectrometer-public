/**
 * Value-axis tick text of the charts. ECharts prints a label with every digit of its value, so an axis end the
 * service computed in binary floating point (a sum's maximum doubled, e.g. 2.0380000000000003) showed its
 * rounding residue. V1.0.3's Matplotlib axes never show such residue; here a label keeps 12 significant digits
 * (far more than any tick needs) and then only the decimals the value has, with ECharts' thousands separators.
 * Only the text changes: the axis range and the plotted values stay the service's.
 */

const SIGNIFICANT_DIGITS = 12;
const MAX_DECIMALS = 20;

export function axisNumber(value: number): string {
  if (!Number.isFinite(value)) return String(value);
  const clean = Number(value.toPrecision(SIGNIFICANT_DIGITS));
  let decimals = 0;
  while (decimals < MAX_DECIMALS && Number(clean.toFixed(decimals)) !== clean) decimals += 1;
  const [whole = "", fraction] = clean.toFixed(decimals).split(".");
  const grouped = whole.replace(/\B(?=(\d{3})+(?!\d))/g, ",");
  return fraction === undefined ? grouped : `${grouped}.${fraction}`;
}
