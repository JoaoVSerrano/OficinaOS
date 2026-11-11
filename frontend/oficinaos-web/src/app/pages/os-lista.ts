import { Component, OnInit, computed, inject, signal } from '@angular/core';
import { Router, RouterLink } from '@angular/router';
import { Api, ApiError, Os, STATUS_LABEL, dataHora, reais } from '../core/api';

@Component({
  selector: 'app-os-lista',
  imports: [RouterLink],
  template: `
    <div class="actions" style="justify-content:space-between;margin-bottom:12px">
      <h1>Ordens de serviço</h1>
      @if (podeAbrir()) { <a class="btn primary" routerLink="/app/os/nova">Abrir ordem de serviço</a> }
    </div>
    <div class="actions" style="margin-bottom:12px" role="group" aria-label="Filtrar por status">
      <button class="btn sm" type="button" [class.primary]="filtro() === ''" (click)="filtro.set('')">Todas</button>
      @for (s of status; track s) {
        <button class="btn sm" type="button" [class.primary]="filtro() === s" (click)="filtro.set(s)">{{ rotulo(s) }}</button>
      }
    </div>
    @if (erro()) { <div class="alert err" role="alert">{{ erro() }}</div> }
    <div class="card">
      @if (carregando()) { <div class="empty">Carregando…</div> }
      @else if (visiveis().length === 0) {
        <div class="empty">Nenhuma ordem de serviço {{ filtro() ? 'com este status' : 'por aqui ainda' }}.
          @if (podeAbrir() && !filtro()) { <div style="margin-top:8px"><a class="btn primary" routerLink="/app/os/nova">Abrir a primeira ordem de serviço</a></div> }</div>
      } @else {
        <div class="table-wrap"><table>
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
  carregando = signal(true);
  erro = signal('');
  visiveis = computed(() => this.ordens().filter((o) => !this.filtro() || o.status === this.filtro()));
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
