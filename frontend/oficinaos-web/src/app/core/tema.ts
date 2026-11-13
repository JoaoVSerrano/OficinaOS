import { Injectable, signal } from '@angular/core';

export type Tema = 'auto' | 'claro' | 'escuro';
const CHAVE = 'oficinaos.tema';

/** Tema da interface: segue o sistema por padrão; a escolha do usuário fica salva só neste navegador. */
@Injectable({ providedIn: 'root' })
export class TemaService {
  readonly tema = signal<Tema>(this.ler());

  constructor() { this.aplicar(this.tema()); }

  alternar() {
    const proximo: Tema = this.efetivo() === 'escuro' ? 'claro' : 'escuro';
    this.tema.set(proximo);
    this.aplicar(proximo);
    try { localStorage.setItem(CHAVE, proximo); } catch { /* navegação privada: segue sem salvar */ }
  }

  efetivo(): 'claro' | 'escuro' {
    const t = this.tema();
    if (t !== 'auto') return t;
    return typeof matchMedia === 'function' && matchMedia('(prefers-color-scheme: dark)').matches ? 'escuro' : 'claro';
  }

  private ler(): Tema {
    try { const v = localStorage.getItem(CHAVE); if (v === 'claro' || v === 'escuro') return v; } catch { /* sem storage */ }
    return 'auto';
  }
  private aplicar(t: Tema) {
    const el = document.documentElement;
    if (t === 'auto') el.removeAttribute('data-theme');
    else el.setAttribute('data-theme', t === 'claro' ? 'light' : 'dark');
  }
}
