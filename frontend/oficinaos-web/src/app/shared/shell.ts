import { Component, computed, inject } from '@angular/core';
import { Router, RouterLink, RouterLinkActive, RouterOutlet } from '@angular/router';
import { Api, PAPEL_LABEL } from '../core/api';

@Component({
  selector: 'app-shell',
  imports: [RouterOutlet, RouterLink, RouterLinkActive],
  styles: [`
    header { background: var(--card); border-bottom: 1px solid var(--line); position: sticky; top: 0; z-index: 5; }
    .bar { display: flex; align-items: center; justify-content: space-between; gap: 12px; padding: 10px 0; flex-wrap: wrap; }
    .logo { font-weight: 800; font-size: 1.15rem; color: var(--ink); text-decoration: none; }
    .logo span { color: var(--brand); }
    nav { display: flex; gap: 4px; flex-wrap: wrap; }
    nav a { padding: .4rem .8rem; border-radius: 8px; text-decoration: none; color: var(--muted); font-weight: 600; }
    nav a.ativo { background: var(--brand-soft); color: var(--brand-dark); }
    .quem { display: flex; align-items: center; gap: 10px; font-size: .88rem; }
    main { padding: 24px 0 48px; }
  `],
  template: `
    <header>
      <div class="container bar">
        <a class="logo" routerLink="/app">Oficina<span>OS</span></a>
        <nav aria-label="Principal">
          @for (item of menu(); track item.link) {
            <a [routerLink]="item.link" routerLinkActive="ativo">{{ item.texto }}</a>
          }
        </nav>
        <div class="quem">
          <span class="muted">{{ user()?.nome }} · {{ papelTexto() }}</span>
          <button class="btn sm" type="button" (click)="sair()">Sair</button>
        </div>
      </div>
    </header>
    <main class="container"><router-outlet /></main>
  `,
})
export class Shell {
  private api = inject(Api);
  private router = inject(Router);
  user = this.api.user;
  papelTexto = computed(() => PAPEL_LABEL[this.user()?.role ?? ''] ?? '');
  menu = computed(() => {
    const papel = this.user()?.role;
    const itens: { link: string; texto: string }[] = [];
    if (papel === 'admin') {
      itens.push({ link: '/app/auditoria', texto: 'Auditoria' });
    } else {
      itens.push({ link: '/app/os', texto: 'Ordens de serviço' });
      if (papel === 'dono' || papel === 'mecanico') itens.push({ link: '/app/clientes', texto: 'Clientes' });
      itens.push({ link: '/app/veiculos', texto: 'Veículos' });
      if (papel === 'dono') itens.push({ link: '/app/equipe', texto: 'Equipe' }, { link: '/app/auditoria', texto: 'Auditoria' });
    }
    itens.push({ link: '/app/perfil', texto: 'Perfil' });
    return itens;
  });
  async sair() {
    await this.api.sair();
    this.router.navigateByUrl('/');
  }
}
