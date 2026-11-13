import { Component, OnInit, computed, inject, signal } from '@angular/core';
import { NavigationEnd, Router, RouterLink, RouterLinkActive, RouterOutlet } from '@angular/router';
import { Api, PAPEL_LABEL } from '../core/api';
import { TemaService } from '../core/tema';

@Component({
  selector: 'app-shell',
  imports: [RouterOutlet, RouterLink, RouterLinkActive],
  styles: [`
    header { background: var(--card); border-bottom: 1px solid var(--line); position: sticky; top: 0; z-index: 5; }
    .bar { display: flex; align-items: center; gap: 12px; padding: 10px 16px; }
    .logo { font-weight: 800; font-size: 1.15rem; color: var(--ink); text-decoration: none; margin-right: 8px; }
    .logo span { color: var(--brand); }
    nav { display: flex; gap: 0; flex: 1; }
    .lado .btn { white-space: nowrap; }
    @media (max-width: 1240px) { .quem { display: none; } }
    nav a { padding: .4rem .6rem; white-space: nowrap; border-radius: 8px; text-decoration: none; color: var(--muted); font-weight: 600; font-size: .92rem; }
    nav a:hover { background: var(--bg); color: var(--ink); }
    nav a.ativo { background: var(--brand-soft); color: var(--brand-dark); }
    .lado { display: flex; align-items: center; gap: 8px; margin-left: auto; }
    .avatar { width: 34px; height: 34px; border-radius: 50%; background: var(--brand-soft); color: var(--brand-dark); font-weight: 800;
      display: grid; place-items: center; font-size: .85rem; flex: none; }
    .quem { line-height: 1.2; font-size: .85rem; } .quem b { display: block; }
    .icone { width: 38px; padding: 0; }
    .menu-btn { display: none; }
    main { padding: 24px 16px 56px; }
    @media (max-width: 900px) {
      .menu-btn { display: inline-flex; }
      nav { display: none; position: absolute; left: 0; right: 0; top: 100%; background: var(--card); border-bottom: 1px solid var(--line);
        flex-direction: column; padding: 8px 16px 12px; box-shadow: var(--shadow); }
      nav.aberto { display: flex; }
      nav a { padding: .7rem .75rem; }
      .nova { display: none; }
      .logo { margin-right: 0; }
    }
  `],
  template: `
    <a class="skip" href="/app/os" (click)="pularParaConteudo($event)">Pular para o conteúdo</a>
    <header>
      <div class="container bar">
        <a class="logo" routerLink="/app">Oficina<span>OS</span></a>
        <button class="btn icone menu-btn" type="button" [attr.aria-expanded]="menuAberto()" aria-controls="menu-principal"
                aria-label="Menu" (click)="menuAberto.set(!menuAberto())">☰</button>
        <nav id="menu-principal" aria-label="Principal" [class.aberto]="menuAberto()" (click)="menuAberto.set(false)">
          @for (item of menu(); track item.link) {
            <a [routerLink]="item.link" routerLinkActive="ativo">{{ item.texto }}</a>
          }
        </nav>
        <div class="lado">
          @if (podeAbrir()) { <a class="btn primary sm nova" routerLink="/app/os/nova">+ Nova OS</a> }
          <button class="btn sm icone" type="button" (click)="tema.alternar()"
                  [attr.aria-label]="tema.efetivo() === 'escuro' ? 'Usar tema claro' : 'Usar tema escuro'">{{ tema.efetivo() === 'escuro' ? '☀' : '☾' }}</button>
          <a class="avatar" routerLink="/app/perfil" [attr.aria-label]="'Meu perfil: ' + user()?.nome" title="Meu perfil">{{ iniciais() }}</a>
          <div class="quem"><b>{{ user()?.nome }}</b><span class="muted">{{ papelTexto() }}</span></div>
          <button class="btn sm" type="button" (click)="sair()">Sair</button>
        </div>
      </div>
    </header>
    <main id="conteudo" class="container" tabindex="-1">
      @if (aviso(); as a) {
        <div class="alert warn" role="alert">{{ a.texto }} <a [routerLink]="'/app/plano'">{{ a.link }}</a></div>
      }
      <router-outlet />
    </main>
  `,
})
export class Shell implements OnInit {
  private api = inject(Api);
  private router = inject(Router);
  tema = inject(TemaService);
  menuAberto = signal(false);
  user = this.api.user;
  iniciais = computed(() => (this.user()?.nome ?? '?').split(/\s+/).filter(Boolean).slice(0, 2).map((p) => p[0].toUpperCase()).join(''));
  podeAbrir = computed(() => ['dono', 'mecanico'].includes(this.user()?.role ?? ''));
  pularParaConteudo(e: Event) { e.preventDefault(); document.getElementById('conteudo')?.focus(); }
  private url = signal(this.router.url);
  /** Aviso global: pagamento falhou ou a cota de OS do Free acabou. Na própria tela do plano ele já aparece. */
  aviso = computed(() => {
    const p = this.api.plano();
    if (!p || this.url().startsWith('/app/plano')) return null;
    if (p.inadimplente) return { texto: 'O último pagamento da assinatura falhou.', link: 'Ver plano e assinatura' };
    const lim = p.limites.max_os_mes;
    if (lim !== null && p.uso.os_mes >= lim) {
      return { texto: `Você usou ${p.uso.os_mes} de ${lim} ordens de serviço deste mês no plano Free.`, link: 'Assinar o Pro' };
    }
    return null;
  });
  ngOnInit() {
    this.router.events.subscribe((e) => { if (e instanceof NavigationEnd) { this.url.set(e.urlAfterRedirects); this.menuAberto.set(false); } });
    this.api.carregarPlano();
  }
  papelTexto = computed(() => PAPEL_LABEL[this.user()?.role ?? ''] ?? '');
  menu = computed(() => {
    const papel = this.user()?.role;
    const itens: { link: string; texto: string }[] = [];
    if (papel === 'admin') {
      itens.push({ link: '/app/admin', texto: 'Painel' }, { link: '/app/auditoria', texto: 'Auditoria' });
    } else {
      itens.push({ link: '/app/os', texto: 'Ordens' });
      if (papel === 'dono' || papel === 'mecanico') itens.push({ link: '/app/clientes', texto: 'Clientes' }, { link: '/app/catalogo', texto: 'Catálogo' });
      itens.push({ link: '/app/veiculos', texto: 'Veículos' });
      if (papel === 'dono') itens.push({ link: '/app/financeiro', texto: 'Financeiro' }, { link: '/app/equipe', texto: 'Equipe' }, { link: '/app/auditoria', texto: 'Auditoria' });
      if (papel === 'dono' || papel === 'mecanico') itens.push({ link: '/app/plano', texto: 'Plano' });
    }
    return itens;
  });
  async sair() {
    await this.api.sair();
    this.router.navigateByUrl('/');
  }
}
