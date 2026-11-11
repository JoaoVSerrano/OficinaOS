import { Component, OnInit, computed, inject, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { Api, ApiError } from '../core/api';

interface Evento { event_id: string; usuario_id: string | null; usuario_nome?: string | null; acao: string; detalhe: string | null;
  papel?: string | null; oficina_id?: string | null; recurso?: string | null; recurso_id?: string | null; ip?: string | null; ts_ms: number; }

@Component({
  selector: 'app-auditoria',
  imports: [FormsModule],
  template: `
    <h1>Auditoria</h1>
    <p class="muted">Quem fez o quê e quando{{ ehAdmin() ? ', em todas as oficinas' : ' na sua oficina' }}.</p>
    @if (erro()) { <div class="alert err" role="alert">{{ erro() }}</div> }
    <form class="card" (ngSubmit)="carregar()">
      <div class="row">
        <div><label for="tipo">Tipo de evento</label>
          <select id="tipo" name="tipo" [(ngModel)]="tipo">
            <option value="">Todos</option>
            @for (t of tipos; track t.valor) { <option [value]="t.valor">{{ t.texto }}</option> }
          </select></div>
        @if (ehAdmin()) { <div><label for="of">Oficina (id)</label><input id="of" name="of" type="number" [(ngModel)]="oficina" placeholder="Todas"></div> }
        <div style="align-self:end"><button class="btn primary" type="submit">Filtrar</button></div>
      </div>
    </form>
    <div class="card">
      @if (eventos().length === 0) { <div class="empty">Nenhum evento encontrado.</div> } @else {
        <div class="table-wrap"><table>
          <thead><tr><th>Quando</th><th>Quem</th><th>Papel</th><th>Evento</th><th>Recurso</th>@if (ehAdmin()) { <th>Oficina</th> }</tr></thead>
          <tbody>
            @for (e of eventos(); track e.event_id) {
              <tr><td class="nowrap">{{ quando(e.ts_ms) }}</td><td>{{ e.usuario_nome || (e.usuario_id ? 'Usuário #' + e.usuario_id : '—') }}</td>
                <td>{{ e.papel || '—' }}</td><td><code>{{ e.acao }}</code></td>
                <td>{{ e.recurso ? e.recurso + ' #' + e.recurso_id : '—' }}</td>@if (ehAdmin()) { <td>{{ e.oficina_id || '—' }}</td> }</tr>
            }
          </tbody>
        </table></div>
      }
    </div>
  `,
})
export class Auditoria implements OnInit {
  private api = inject(Api);
  ehAdmin = computed(() => this.api.user()?.role === 'admin');
  eventos = signal<Evento[]>([]);
  erro = signal(''); tipo = ''; oficina: number | null = null;
  tipos = [
    { valor: 'os.', texto: 'Ordens de serviço (todos)' }, { valor: 'os.aberta', texto: 'OS aberta' },
    { valor: 'os.status_alterado', texto: 'Status alterado' }, { valor: 'os.orcamento_aprovado', texto: 'Orçamento aprovado' },
    { valor: 'os.excluida', texto: 'OS excluída' }, { valor: 'anexo.enviado', texto: 'Anexo enviado' },
    { valor: 'acesso_negado', texto: 'Acesso negado' }, { valor: 'plano.limite_atingido', texto: 'Limite do plano' },
    { valor: 'login', texto: 'Login' },
  ];
  quando = (ms: number) => new Date(ms).toLocaleString('pt-BR', { dateStyle: 'short', timeStyle: 'medium' });

  async ngOnInit() { await this.carregar(); }
  async carregar() {
    this.erro.set('');
    const params: Record<string, string | number> = { n: 100 };
    if (this.tipo) params['acao'] = this.tipo;
    if (this.ehAdmin() && this.oficina) params['oficina_id'] = this.oficina;
    try {
      const url = this.ehAdmin() ? '/api/admin/logs' : '/api/auditoria';
      this.eventos.set((await this.api.get<{ logs: Evento[] }>(url, params)).logs);
    } catch (e) { this.erro.set((e as ApiError).message); }
  }
}
