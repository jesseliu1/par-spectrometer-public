/**
 * The company's brand on the page (V1.0.3 par_app/ui.py: BRAND_LOGO_PATH, COMPANY_NAME, SUPPORT_CONTACT,
 * SUPPORT_EMAIL, COMPANY_WEBSITE, COMPANY_ADDRESS and the 关于与技术支持 group). The logo is the repository's
 * logo.png, the same file the window and V1.0.3 use; tests/unit/test_web_brand.py keeps the texts equal to V1.0.3's.
 */
import logoUrl from "../../../logo.png";

export const LOGO_URL: string = logoUrl;
export const PRODUCT_NAME = "PAR 光谱仪专用软件";
export const PRODUCT_MODEL = "ASMART-GROW-SPECTRA I";
export const BRAND_NAME = "PAR 光谱仪";
export const SUPPORT_CONTACT = "请通过电子邮件联系";
export const SUPPORT_EMAIL = "jesse.sijia.liu@gmail.com";
export const PRODUCT_PURPOSE =
  "面向温室、植物工厂与农业科研的光环境测量与分析工具。支持光谱采集、历史回放、光谱计算、日累计光积分及数据导出。";

/** What customers see of the build version: "2.0.0-alpha.6" reads "构建 6" (no "alpha" on the page, issue 119);
 * any other form is shown as it is. The full version stays in build_manifest.json and the diagnostics bundle. */
export function buildLabel(version: string): string {
  const match = /^\d+\.\d+\.\d+-alpha\.(\d+)$/.exec(version);
  return match ? `构建 ${match[1]}` : version;
}
