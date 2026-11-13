import { Component, OnInit, computed, inject, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { Api, ApiError, reais } from '../../core/api';
import { FORMA_LABEL, hojeBrasilia } from '../os/os-pagamentos';

interface Resumo {
  mes: string; faturado_centavos: number; por_forma: Record<string, number>; os_entregues: number;
  ticket_medio_centavos: number; a_receber_centavos: number;
}

/** Resumo financeiro do mês (só o dono; o backend recusa os outros papéis). */
@Component({
  selector: 'app-financeiro',
  imports: [FormsModule],
  template: `
    <div class="actions" style="justify-content:space-between;margin-bottom:8px">
      <h1>Financeiro</h1>
      <div class="field" style="margin:0"><label for="fin-mes">Mês</label>
        <input id="fin-mes" type="month" [ngModel]="mes()" (ngModelChange)="trocarMes($event)" [max]="mesAtual"></div>
    </div>
    <p class="muted small">O faturado conta cada pagamento pelo dia em que foi recebido; "a receber" é a posição de hoje, em qualquer mês.</p>
    @if (erro()) { <div class="alert err" role="alert">{{ erro() }}</div> }

    @if (resumo(); as r) {
      <div class="row">
        <div class="card"><span class="muted small">Faturado no mês</span><div style="font-size:1.5rem"><strong>{{ dinheiro(r.faturado_centavos) }}</strong></div></div>
        <div class="card"><span class="muted small">A receber (hoje)</span><div style="font-size:1.5rem"><strong>{{ dinheiro(r.a_receber_centavos) }}</strong></div></div>
        <div class="card"><span class="muted small">OS entregues</span><div style="font-size:1.5rem"><strong>{{ r.os_entregues }}</strong></div></div>
        <div class="card"><span class="muted small">Ticket médio</span><div style="font-size:1.5rem"><strong>{{ dinheiro(r.ticket_medio_centavos) }}</strong></div></div>
      </div>

      <div class="card">
        <h2>Por forma de pagamento</h2>
        @if (formas().length) {
          <div class="table-wrap"><table>
            <thead><tr><th>Forma</th><th class="right">Recebido</th><th class="right">Participação</th></tr></thead>
            <tbody>
              @for (f of formas(); track f.forma) {
                <tr><td>{{ f.rotulo }}</td><td class="right nowrap">{{ dinheiro(f.valor) }}</td><td class="right">{{ f.pct }}</td></tr>
              }
            </tbody>
            <tfoot><tr><th class="right">Total</th><th class="right nowrap">{{ dinheiro(r.faturado_centavos) }}</th><th></th></tr></tfoot>
          </table></div>
        } @else { <p class="muted empty">Nenhum pagamento recebido neste mês.</p> }
      </div>
    } @else if (!erro()) { <p class="muted">Carregando…</p> }
  `,
})
export class Financeiro implements OnInit {
  private api = inject(Api);
  readonly mesAtual = hojeBrasilia().slice(0, 7);
  mes = signal(this.mesAtual);
  resumo = signal<Resumo | null>(null);
  erro = signal('');
  dinheiro = reais;

  formas = computed(() => {
    const r = this.resumo();
    if (!r) return [];
    return Object.entries(r.por_forma).sort((a, b) => b[1] - a[1]).map(([forma, valor]) => ({
      forma, valor, rotulo: FORMA_LABEL[forma] ?? forma,
      pct: r.faturado_centavos ? Math.round((valor * 100) / r.faturado_centavos) + '%' : '—',
    }));
  });

  ngOnInit() { return this.carregar(); }

  trocarMes(valor: string) {
    if (!/^\d{4}-(0[1-9]|1[0-2])$/.test(valor ?? '')) return;
    this.mes.set(valor);
    return this.carregar();
  }

  async carregar() {
    this.erro.set('');
    try { this.resumo.set(await this.api.get<Resumo>('/api/financeiro/resumo', { mes: this.mes() })); }
    catch (e) { this.resumo.set(null); this.erro.set((e as ApiError).message); }
  }
}
