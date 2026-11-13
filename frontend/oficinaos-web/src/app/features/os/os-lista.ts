import { Component, OnInit, computed, inject, signal } from '@angular/core';
import { Router, RouterLink } from '@angular/router';
import { Api, ApiError, Os, STATUS_LABEL, dataHora, reais } from '../../core/api';

@Component({
  selector: 'app-os-lista',
  imports: [RouterLink],
  template: `
    <div class="page-head">
      <div><h1>Ordens de serviço</h1>
        <p class="muted">{{ resumo() }}</p></div>
      @if (podeAbrir()) { <a class="btn primary" routerLink="/app/os/nova">+ Abrir ordem de serviço</a> }
    </div>
    <div class="search">
      <svg viewBox="0 0 20 20" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true"><circle cx="9" cy="9" r="6"/><path d="m14 14 4 4"/></svg>
      <input type="search" aria-label="Buscar por placa, cliente ou problema" placeholder="Buscar por placa, cliente ou problema"
             [value]="busca()" (input)="busca.set($any($event.target).value)">
    </div>
    <div class="chips" role="group" aria-label="Filtrar por status">
      <button class="chip" type="button" [attr.aria-pressed]="filtro() === ''" (click)="filtro.set('')">Todas <span class="n">{{ ordens().length }}</span></button>
      @for (s of status; track s) {
        <button class="chip" type="button" [attr.aria-pressed]="filtro() === s" (click)="filtro.set(s)">{{ rotulo(s) }} <span class="n">{{ contagem()[s] || 0 }}</span></button>
      }
    </div>
    @if (erro()) { <div class="alert err" role="alert">{{ erro() }}</div> }
    <div class="card">
      @if (carregando()) { <div class="empty" role="status">Carregando…</div> }
      @else if (visiveis().length === 0) {
        <div class="empty">
          @if (filtro() || busca()) { Nenhuma ordem de serviço encontrada. <div style="margin-top:8px"><button class="btn sm" type="button" (click)="limpar()">Limpar filtros</button></div> }
          @else { Nenhuma ordem de serviço por aqui ainda.
            @if (podeAbrir()) { <div style="margin-top:8px"><a class="btn primary" routerLink="/app/os/nova">Abrir a primeira ordem de serviço</a></div> } }
        </div>
      } @else {
        <div class="table-wrap tabela-os"><table>
          <thead><tr><th>Nº</th><th>Veículo</th><th>Cliente</th><th>Problema</th><th>Status</th><th class="right">Total</th><th>Aberta em</th></tr></thead>
          <tbody>
            @for (o of visiveis(); track o.id) {
              <tr class="click" (click)="abrir(o.id)">
                <td><a [routerLink]="['/app/os', o.id]" (click)="$event.stopPropagation()">#{{ o.id }}</a></td>
                <td>{{ o.veiculo?.placa }} <span class="muted small">{{ o.veiculo?.marca }} {{ o.veiculo?.modelo }}</span></td>
                <td>{{ o.cliente?.nome }}</td>
                <td>{{ o.descricao }}</td>
                <td><span class="badge" [class]="'badge ' + o.status">{{ rotulo(o.status) }}</span></td>
                <td class="right nowrap">{{ dinheiro(o.valor_total_centavos) }}</td>
                <td class="nowrap">{{ quando(o.criada_em) }}</td>
              </tr>
            }
          </tbody>
        </table></div>
        <div class="lista-cards">
          @for (o of visiveis(); track o.id) {
            <a class="os-card" [routerLink]="['/app/os', o.id]">
              <div class="topo"><span><span class="placa">{{ o.veiculo?.placa }}</span> <span class="muted small">#{{ o.id }}</span></span>
                <span class="badge" [class]="'badge ' + o.status">{{ rotulo(o.status) }}</span></div>
              <div>{{ o.descricao }}</div>
              <div class="muted small">{{ o.cliente?.nome }} · {{ dinheiro(o.valor_total_centavos) }}</div>
            </a>
          }
        </div>
      }
    </div>
  `,
})
export class OsLista implements OnInit {
  private api = inject(Api);
  private router = inject(Router);
  status = Object.keys(STATUS_LABEL);
  ordens = signal<Os[]>([]);
  filtro = signal('');
  busca = signal('');
  carregando = signal(true);
  erro = signal('');
  contagem = computed(() => {
    const c: Record<string, number> = {};
    for (const o of this.ordens()) c[o.status] = (c[o.status] ?? 0) + 1;
    return c;
  });
  visiveis = computed(() => {
    const q = this.busca().trim().toLowerCase();
    return this.ordens().filter((o) => (!this.filtro() || o.status === this.filtro())
      && (!q || [o.veiculo?.placa, o.veiculo?.marca, o.veiculo?.modelo, o.cliente?.nome, o.descricao].some((t) => (t ?? '').toLowerCase().includes(q))));
  });
  resumo = computed(() => {
    const c = this.contagem();
    const andamento = (c['aberta'] ?? 0) + (c['orcamento_aprovado'] ?? 0) + (c['em_servico'] ?? 0);
    return `${andamento} em andamento · ${c['pronta'] ?? 0} pronta(s) para entregar`;
  });
  limpar() { this.filtro.set(''); this.busca.set(''); }
  podeAbrir = computed(() => ['dono', 'mecanico'].includes(this.api.user()?.role ?? ''));
  rotulo = (s: string) => STATUS_LABEL[s] ?? s;
  dinheiro = reais; quando = dataHora;

  async ngOnInit() {
    try { this.ordens.set((await this.api.get<{ ordens: Os[] }>('/api/os')).ordens); }
    catch (e) { this.erro.set((e as ApiError).message); }
    finally { this.carregando.set(false); }
  }
  abrir(id: number) { this.router.navigate(['/app/os', id]); }
}
