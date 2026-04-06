// Lightweight syntax highlighting using CSS classes
// Avoids the heavy shiki bundle; can be replaced with shiki later if needed

const LANG_KEYWORDS: Record<string, RegExp> = {
  python: /\b(def|class|import|from|return|if|elif|else|for|while|try|except|finally|with|as|async|await|yield|raise|pass|break|continue|and|or|not|in|is|None|True|False|self|lambda)\b/g,
  typescript: /\b(const|let|var|function|return|if|else|for|while|do|switch|case|break|continue|class|interface|type|export|import|from|async|await|new|this|throw|try|catch|finally|typeof|instanceof|void|null|undefined|true|false)\b/g,
  javascript: /\b(const|let|var|function|return|if|else|for|while|do|switch|case|break|continue|class|export|import|from|async|await|new|this|throw|try|catch|finally|typeof|instanceof|void|null|undefined|true|false)\b/g,
  sql: /\b(SELECT|FROM|WHERE|INSERT|UPDATE|DELETE|CREATE|ALTER|DROP|TABLE|INDEX|JOIN|LEFT|RIGHT|INNER|ON|AND|OR|NOT|IN|IS|NULL|ORDER|BY|GROUP|HAVING|LIMIT|OFFSET|AS|SET|VALUES|INTO)\b/gi,
}

const LANG_MAP: Record<string, string> = {
  py: 'python',
  ts: 'typescript',
  tsx: 'typescript',
  js: 'javascript',
  jsx: 'javascript',
  json: 'javascript',
  yaml: 'python',
  yml: 'python',
  sql: 'sql',
  md: 'python',
}

export function detectLanguage(path: string): string {
  const ext = path.split('.').pop()?.toLowerCase() ?? ''
  return LANG_MAP[ext] ?? 'text'
}

export function highlightCode(code: string, language: string): string {
  const keywords = LANG_KEYWORDS[language]
  if (!keywords) return escapeHtml(code)

  // Escape HTML first
  let html = escapeHtml(code)

  // Highlight strings
  html = html.replace(/(["'`])(?:(?!\1|\\).|\\.)*\1/g, '<span style="color:var(--tertiary)">$&</span>')

  // Highlight comments
  html = html.replace(/(\/\/.*$|#.*$)/gm, '<span style="color:var(--outline)">$&</span>')

  // Highlight keywords
  html = html.replace(keywords, '<span style="color:var(--primary)">$&</span>')

  // Highlight numbers
  html = html.replace(/\b(\d+\.?\d*)\b/g, '<span style="color:var(--amber)">$&</span>')

  return html
}

function escapeHtml(text: string): string {
  return text
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
}
