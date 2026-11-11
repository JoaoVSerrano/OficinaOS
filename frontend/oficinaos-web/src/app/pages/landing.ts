import { Component, OnInit, inject } from '@angular/core';
import { ActivatedRoute, Router, RouterLink } from '@angular/router';
import { Api } from '../core/api';

@Component({
  selector: 'app-landing',
  imports: [RouterLink],
  styles: [`
    .topo { background: var(--card); border-bottom: 1px solid var(--line); }
    .barra { display: flex; justify-content: space-between; align-items: center; padding: 12px 0; }
    .logo { font-weight: 800; font-size: 1.2rem; text-decoration: none; color: var(--ink); } .logo span { color: var(--brand); }
    .hero { padding: 64px 0 40px; text-align: center; }
    .hero h1 { font-size: clamp(2rem, 5vw, 3.2rem); max-width: 18ch; margin: 0 auto 1rem; }
    .hero p { font-size: 1.15rem; max-width: 56ch; margin: 0 auto 1.5rem; color: var(--muted); }
    .grid3 { display: grid; gap: 16px; grid-template-columns: repeat(auto-fit, minmax(260px, 1fr)); margin: 24px 0; }
    .grid3 .card { margin: 0; } .icone { font-size: 1.8rem; }
    .planos { display: grid; gap: 16px; grid-template-columns: repeat(auto-fit, minmax(260px, 1fr)); max-width: 720px; margin: 0 auto; }
    .planos .destaque { border: 2px solid var(--brand); }
    .preco { font-size: 1.8rem; font-weight: 800; } ul { padding-left: 1.1rem; margin: .5rem 0 1rem; } li { margin: .25rem 0; }
    section { padding: 24px 0; } section > h2 { text-align: center; margin-bottom: 1.2rem; font-size: 1.5rem; }
    footer { border-top: 1px solid var(--line); padding: 24px 0; text-align: center; color: var(--muted); font-size: .9rem; }
  `],
  template: `
    <header class="topo">
      <div class="container barra">
        <a class="logo" routerLink="/">Oficina<span>OS</span></a>
        <div class="actions">
          @if (logado()) { <a class="btn primary" routerLink="/app">Abrir meu painel</a> }
          @else { <a class="btn" routerLink="/entrar">Entrar</a><a class="btn primary" routerLink="/cadastro">Criar conta grátis</a> }
        </div>
      </div>
    </header>
    <main>
      <div class="container">
        <section class="hero">
          <h1>Pare de perder serviço no caderno</h1>
          <p>O OficinaOS organiza as ordens de serviço da sua oficina: cada carro com status, fotos e orçamento aprovado pelo cliente, tudo em um só lugar.</p>
          <a class="btn primary" routerLink="/cadastro">Criar conta grátis</a>
        </section>

        <section aria-labelledby="beneficios">
          <h2 id="beneficios">Feito para oficinas pequenas</h2>
          <div class="grid3">
            <div class="card"><div class="icone" aria-hidden="true">📋</div><h3>Ordem de serviço com status</h3>
              <p class="muted">Da abertura à entrega: aberta, orçamento aprovado, em serviço, pronta e entregue. Ninguém precisa perguntar "como está o carro?".</p></div>
            <div class="card"><div class="icone" aria-hidden="true">📷</div><h3>Histórico do veículo com fotos</h3>
              <p class="muted">Registre a entrada do carro, as peças trocadas e os comprovantes. Tudo fica ligado à ordem de serviço certa.</p></div>
            <div class="card"><div class="icone" aria-hidden="true">✅</div><h3>Orçamento aprovado pelo cliente</h3>
              <p class="muted">O cliente entra com a conta dele, vê o orçamento do próprio veículo e aprova. Sem recado perdido no WhatsApp.</p></div>
          </div>
        </section>

        <section aria-labelledby="planos">
          <h2 id="planos">Planos</h2>
          <div class="planos">
            <div class="card"><h3>Free</h3><div class="preco">R$ 0</div>
              <ul><li>20 ordens de serviço por mês</li><li>1 mecânico</li><li>3 fotos por ordem de serviço</li></ul>
              <a class="btn block" routerLink="/cadastro">Criar conta grátis</a></div>
            <div class="card destaque"><h3>Pro</h3><div class="preco">R$ 49<span class="small muted">/mês</span></div>
              <ul><li>Ordens de serviço sem limite</li><li>Mecânicos sem limite</li><li>Fotos sem limite</li></ul>
              <a class="btn primary block" routerLink="/cadastro">Começar no Free e assinar depois</a></div>
          </div>
        </section>
      </div>
    </main>
    <footer>
      <div class="container">OficinaOS · projeto da disciplina ISW055 — Introdução à Computação em Nuvem · Fatec Pompeia</div>
    </footer>
  `,
})
export class Landing implements OnInit {
  private api = inject(Api);
  private router = inject(Router);
  private route = inject(ActivatedRoute);
  logado = () => !!this.api.user();

  async ngOnInit() {
    await this.api.garantirUsuario();
    const q = this.route.snapshot.queryParamMap;
    if (q.get('payment') && this.api.user()) this.router.navigate(['/app/plano'], { queryParams: { payment: q.get('payment') } });
    else if (q.get('google_login') && this.api.user()) this.router.navigateByUrl('/app');
  }
}
