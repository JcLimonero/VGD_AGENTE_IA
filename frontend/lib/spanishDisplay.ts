/**
 * Con teclado incorrecto suele escribirse `;` en lugar de `ñ` (p. ej. «año» → «a;o»).
 * Solo corrige formas muy frecuentes en títulos de consultas y widgets.
 */
export function fixSpanishSemicolonEnyeTypo(text: string): string {
  if (!text.includes(';')) return text
  return text
    .replace(/\bni;os\b/g, 'niños')
    .replace(/\bni;as\b/g, 'niñas')
    .replace(/\bni;o\b/g, 'niño')
    .replace(/\bni;a\b/g, 'niña')
    .replace(/\bNi;OS\b/g, 'NIÑOS')
    .replace(/\bNi;AS\b/g, 'NIÑAS')
    .replace(/\bNi;O\b/g, 'NIÑO')
    .replace(/\bNi;A\b/g, 'NIÑA')
    .replace(/\ba;os\b/g, 'años')
    .replace(/\ba;o\b/g, 'año')
    .replace(/\bA;OS\b/g, 'AÑOS')
    .replace(/\bA;O\b/g, 'AÑO')
}
