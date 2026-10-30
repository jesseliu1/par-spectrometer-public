// R-1-5: no scattered colours. Colour values may appear only in src/styles/tokens.css: hex, the CSS colour
// functions (rgb/rgba, hsl/hsla, hwb, lab, lch, oklab, oklch, color, color-mix) and CSS named colours given to a
// colour property (color, background, border…, fill, stroke, …Color keys in ECharts options); transparent and
// currentColor are allowed. Every other file under src/ every other file under src/ must use the tokens (var(--…) in CSS, src/lib/theme.ts in
// code). Usage: node scripts/check-tokens.mjs [root]  (exit 1 and a list of file:line on violations)
import { readdirSync, readFileSync, statSync } from "node:fs";
import { join, relative, sep } from "node:path";
import { fileURLToPath } from "node:url";

const TOKENS = join("styles", "tokens.css");
const CHECKED = /\.(vue|ts|css|html)$/;
const COLOUR = /#[0-9a-fA-F]{3,8}\b(?![-\w])|(?<![\w-])(?:rgba?|hsla?|hwb|lab|lch|oklab|oklch|color|color-mix)\s*\(/i;
const PROPERTY = /([\w-]+)["']?\s*:\s*([^;{}\n]*)/g;
const COLOUR_PROPERTY = /colou?r|background|border|outline|fill|stroke|shadow/i;
const WORD = /(?<![\w-])[a-z]+(?![\w-])/gi;
// CSS Color Module Level 4 named colours (transparent and currentColor are allowed and therefore not listed)
const NAMED = new Set(
  (
    "aliceblue antiquewhite aqua aquamarine azure beige bisque black blanchedalmond blue blueviolet brown " +
    "burlywood cadetblue chartreuse chocolate coral cornflowerblue cornsilk crimson cyan darkblue darkcyan " +
    "darkgoldenrod darkgray darkgreen darkgrey darkkhaki darkmagenta darkolivegreen darkorange darkorchid darkred " +
    "darksalmon darkseagreen darkslateblue darkslategray darkslategrey darkturquoise darkviolet deeppink " +
    "deepskyblue dimgray dimgrey dodgerblue firebrick floralwhite forestgreen fuchsia gainsboro ghostwhite gold " +
    "goldenrod gray green greenyellow grey honeydew hotpink indianred indigo ivory khaki lavender lavenderblush " +
    "lawngreen lemonchiffon lightblue lightcoral lightcyan lightgoldenrodyellow lightgray lightgreen lightgrey " +
    "lightpink lightsalmon lightseagreen lightskyblue lightslategray lightslategrey lightsteelblue lightyellow lime " +
    "limegreen linen magenta maroon mediumaquamarine mediumblue mediumorchid mediumpurple mediumseagreen " +
    "mediumslateblue mediumspringgreen mediumturquoise mediumvioletred midnightblue mintcream mistyrose moccasin " +
    "navajowhite navy oldlace olive olivedrab orange orangered orchid palegoldenrod palegreen paleturquoise " +
    "palevioletred papayawhip peachpuff peru pink plum powderblue purple rebeccapurple red rosybrown royalblue " +
    "saddlebrown salmon sandybrown seagreen seashell sienna silver skyblue slateblue slategray slategrey snow " +
    "springgreen steelblue tan teal thistle tomato turquoise violet wheat white whitesmoke yellow yellowgreen"
  ).split(" "),
);

function hasColour(line) {
  if (COLOUR.test(line)) return true;
  for (const [, name, value] of line.matchAll(PROPERTY)) {
    if (!COLOUR_PROPERTY.test(name)) continue;
    for (const [word] of value.matchAll(WORD)) if (NAMED.has(word.toLowerCase())) return true;
  }
  return false;
}

function* files(dir) {
  for (const name of readdirSync(dir)) {
    const path = join(dir, name);
    if (statSync(path).isDirectory()) yield* files(path);
    else if (CHECKED.test(name)) yield path;
  }
}

export function violations(base) {
  const found = [];
  for (const path of files(base)) {
    const name = relative(base, path);
    if (name === TOKENS || name.split(sep).join("/") === "styles/tokens.css") continue;
    readFileSync(path, "utf-8")
      .split("\n")
      .forEach((line, index) => {
        if (hasColour(line)) found.push(`${name}:${index + 1}: ${line.trim()}`);
      });
  }
  return found;
}

if (process.argv[1] !== undefined && fileURLToPath(import.meta.url) === process.argv[1]) {
  const root = process.argv[2] ?? join(fileURLToPath(new URL("..", import.meta.url)), "src");
  const found = violations(root);
  if (found.length) {
    console.error(`colour values outside src/styles/tokens.css (R-1-5):\n${found.join("\n")}`);
    process.exit(1);
  }
  console.log("tokens: no colour values outside src/styles/tokens.css");
}
