// Organfärger och förkortningar (design.md, Organfärger, #166). Färgen följer organet i alla vyer och står
// alltid bredvid förkortningen eller namnet, aldrig ensam. Ett okänt organ får en neutral markering.

const FARG: Record<string, string> = {
  KF: 'var(--organ-kf)',
  KS: 'var(--organ-ks)',
  SAM: 'var(--organ-sam)',
  SOC: 'var(--organ-soc)',
  SKOL: 'var(--organ-skol)',
}

/** Organets färg som CSS-värde, `--ink-muted` för ett okänt organ. */
export function organfarg(id: string): string {
  return FARG[id.toUpperCase()] ?? 'var(--ink-muted)'
}

/** Organets förkortning: KF, KS, SAM, SOC och SKOL, annars id:t i versaler. */
export function organforkortning(id: string): string {
  return id.toUpperCase()
}
