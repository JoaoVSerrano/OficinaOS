import { Component, OnInit, inject, signal } from '@angular/core';
import { Api, ApiError, dataHora, reais } from '../core/api';

interface Painel {
  oficinas_por_plano: { free: number; pro: number };
  usuarios_por_plano: { free: number; pro: number; sem_oficina: number };
  assinaturas_ativas: number;
  inadimplentes: number;
  mrr_centavos: number;
  moeda: string;
  eventos: { event_id: string; acao: string; usuario_id: string | null; papel?: string | null;
    oficina_id?: string | null; ts_ms: number }[];
}

@Component({
  selector: 'app-admin',
  styles: [`
    .kpis { display: grid; gap: 12px; grid-template-columns: repeat(auto-fit, minmax(210px, 1fr)); margin-bottom: 16px; }
    .kpi { margin: 0; }
    .kpi .valor { font-size: 1.8rem; font-weight: 700; line-height: 1.2; }
    .kpi .rotulo { color: var(--muted, #667); font-size: .9rem; }
  `],
  template: `
    <h1>Painel da plataforma</h1>
    <p class="muted">Visão de todas as oficinas. O MRR é de <strong>teste</strong>: soma mensal das assinaturas ativas na Stripe em modo de teste.</p>
    @if (erro()) { <div class="alert err" role="alert">{{ erro() }}</div> }
    @if (p(); as d) {
      <section class="kpis" aria-label="Indicadores">
        <div class="card kpi"><div class="rotulo">MRR de teste</div><div class="valor">{{ reais(d.mrr_centavos) }}</div></div>
        <div class="card kpi"><div class="rotulo">Assinaturas ativas</div><div class="valor">{{ d.assinaturas_ativas }}</div>
          @if (d.inadimplentes) { <div class="rotulo">{{ d.inadimplentes }} inadimplente(s)</div> }</div>
        <div class="card kpi"><div class="rotulo">Oficinas no Free</div><div class="valor">{{ d.oficinas_por_plano.free }}</div></div>
        <div class="card kpi"><div class="rotulo">Oficinas no Pro</div><div class="valor">{{ d.oficinas_por_plano.pro }}</div></div>
      </section>
      <div class="card">
        <h2>Usuários por plano</h2>
        <div class="table-wrap"><table>
          <thead><tr><th>Plano</th><th>Usuários</th></tr></thead>
          <tbody>
            <tr><td>Free</td><td>{{ d.usuarios_por_plano.free }}</td></tr>
            <tr><td>Pro</td><td>{{ d.usuarios_por_plano.pro }}</td></tr>
            <tr><td>Sem oficina ainda</td><td>{{ d.usuarios_por_plano.sem_oficina }}</td></tr>
          </tbody>
        </table></div>
      </div>
      <div class="card">
        <h2>Últimos eventos</h2>
        @if (d.eventos.length === 0) { <div class="empty">Nenhum evento ainda.</div> } @else {
          <div class="table-wrap"><table>
            <thead><tr><th>Quando</th><th>Evento</th><th>Papel</th><th>Oficina</th></tr></thead>
            <tbody>
              @for (e of d.eventos; track e.event_id) {
                <tr><td class="nowrap">{{ quando(e.ts_ms) }}</td><td><code>{{ e.acao }}</code></td>
                  <td>{{ e.papel || '—' }}</td><td>{{ e.oficina_id || '—' }}</td></tr>
              }
            </tbody>
          </table></div>
        }
      </div>
    } @else if (!erro()) { <p class="muted">Carregando…</p> }
  `,
})
export class Admin implements OnInit {
  private api = inject(Api);
  p = signal<Painel | null>(null);
  erro = signal('');
  reais = reais;
  quando = (ms: number) => dataHora(new Date(ms).toISOString());

  async ngOnInit() {
    try { this.p.set(await this.api.get<Painel>('/api/admin/painel')); }
    catch (e) { this.erro.set((e as ApiError).message); }
  }
}
