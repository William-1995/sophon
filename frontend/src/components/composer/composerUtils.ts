export function composePlaceholder(base: string) {
  if (base.includes('Enter to send') || base.includes('Shift+Enter')) {
    return base
  }
  return `${base} · Enter to send · Shift+Enter newline`
}

export function createStableInputId(prefix: string, rawId: string) {
  return `${prefix}-${rawId.replace(/:/g, '')}`
}

export function createAttachmentId() {
  return `${Date.now()}-${Math.random().toString(36).slice(2, 9)}`
}
