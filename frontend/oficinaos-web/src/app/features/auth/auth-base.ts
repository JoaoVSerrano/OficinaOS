export const AUTH_STYLES = `
  .wrap { min-height: 100vh; display: grid; place-items: center; padding: 24px 16px; }
  .box { width: 100%; max-width: 440px; }
  .logo { display: block; text-align: center; font-weight: 800; font-size: 1.4rem; text-decoration: none; color: var(--ink); margin-bottom: 16px; }
  .logo span { color: var(--brand); }
  .links { display: flex; justify-content: space-between; gap: 8px; flex-wrap: wrap; margin-top: 12px; font-size: .9rem; }
  fieldset { border: 0; padding: 0; margin: 0 0 1rem; }
  legend { font-weight: 600; font-size: .9rem; margin-bottom: .4rem; padding: 0; }
  .opcoes { display: grid; gap: 8px; grid-template-columns: repeat(3, 1fr); }
  .opcao { border: 1px solid var(--line); border-radius: 10px; padding: .6rem; text-align: center; cursor: pointer; font-weight: 600; margin: 0; }
  .opcao input { position: absolute; opacity: 0; width: 1px; min-height: 0; }
  .opcao.on { border: 2px solid var(--brand); background: var(--brand-soft); }
  .opcao:has(input:focus-visible) { outline: 2px solid var(--brand); outline-offset: 2px; }
`;
