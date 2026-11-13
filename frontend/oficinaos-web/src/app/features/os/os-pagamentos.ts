import { Component, computed, effect, inject, input, output, signal, untracked } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { Api, ApiError, Os, paraCentavos, reais } from '../../core/api';

export interface Pagamento {
  id: number; valor_centavos: number; forma: string; pago_em: string; observacao: string | null; registrado_por: number;
}
export interface SituacaoPagamento {
  pagamentos: Pagamento[]; valor_devido_centavos: number; pago_centavos: number; saldo_centavos: number;
}

export const FORMA_LABEL: Record<string, string> = {
  dinheiro: 'Dinheiro', pix: 'Pix', cartao_credito: 'Cartão de crédito', cartao_debito: 'Cartão de débito',
  boleto: 'Boleto', outro: 'Outro',
};

/** "AAAA-MM-DD" de hoje em Brasília (mesmo referencial do backend). */
export function hojeBrasilia(): string {
  return new Date().toLocaleDateString('sv-SE', { timeZone: 'America/Sao_Paulo' });
}
/** "AAAA-MM-DD" -> "DD/MM/AAAA" sem passar por Date (evita deslocamento de fuso). */
export function dataCurta(iso: string | null | undefined): string {
  if (!iso) return '';
  const [a, m, d] = iso.slice(0, 10).split('-');
  return `${d}/${m}/${a}`;
}
/** 4590 -> "45,90" (formato aceito por paraCentavos). */
function paraTexto(centavos: number): string {
  return (centavos / 100).toFixed(2).replace('.', ',');
}

/** Pagamentos da OS: só o dono vê e registra (o backend também recusa os outros papéis). */
@Component({
  selector: 'app-os-pagamentos',
  imports: [FormsModule],
  template: `
    @if (visivel(); as s) {
      <div class="card">
        <h2>Pagamento</h2>
        @if (erro()) { <div class="alert err" role="alert">{{ erro() }}</div> }
        @if (aviso()) { <div class="alert ok" role="status">{{ aviso() }}</div> }
        <div class="row">
          <div><span class="muted small">Valor devido</span><div><strong>{{ dinheiro(s.valor_devido_centavos) }}</strong></div></div>
          <div><span class="muted small">Pago</span><div>{{ dinheiro(s.pago_centavos) }}</div></div>
          <div><span class="muted small">Saldo</span>
            @if (s.saldo_centavos === 0 && s.valor_devido_centavos > 0) {
              <div><span class="badge entregue">Quitado</span></div>
            } @else { <div><strong>{{ dinheiro(s.saldo_centavos) }}</strong></div> }
          </div>
        </div>

        @if (s.pagamentos.length) {
          <div class="table-wrap" style="margin-top:12px"><table>
            <thead><tr><th>Data</th><th>Forma</th><th class="right">Valor</th><th>Observação</th><th></th></tr></thead>
            <tbody>
              @for (p of s.pagamentos; track p.id) {
                <tr><td class="nowrap">{{ data(p.pago_em) }}</td><td>{{ forma(p.forma) }}</td>
                  <td class="right nowrap">{{ dinheiro(p.valor_centavos) }}</td><td>{{ p.observacao }}</td>
                  <td class="right">
                    @if (removendo() === p.id) {
                      <span class="small">Remover?</span>
                      <button class="btn danger sm" type="button" (click)="remover(p.id)">Sim</button>
                      <button class="btn sm" type="button" (click)="removendo.set(null)">Não</button>
                    } @else {
                      <button class="btn sm" type="button" (click)="removendo.set(p.id)"
                        [attr.aria-label]="'Remover pagamento de ' + dinheiro(p.valor_centavos)">Remover</button>
                    }
                  </td></tr>
              }
            </tbody>
          </table></div>
        } @else { <p class="muted" style="margin-top:12px">Nenhum pagamento registrado. Entregar sem pagamento deixa o valor em "a receber".</p> }

        @if (podeRegistrar()) {
          <form (ngSubmit)="registrar()" style="margin-top:12px">
            <div class="row">
              <div class="field"><label for="pag-valor">Valor (R$)</label>
                <input id="pag-valor" name="valor" inputmode="decimal" [(ngModel)]="form.valor" placeholder="0,00" required></div>
              <div class="field"><label for="pag-forma">Forma</label>
                <select id="pag-forma" name="forma" [(ngModel)]="form.forma">
                  @for (f of formas; track f) { <option [value]="f">{{ forma(f) }}</option> }
                </select></div>
              <div class="field"><label for="pag-data">Data</label>
                <input id="pag-data" name="pago_em" type="date" [(ngModel)]="form.pago_em" [max]="hoje()" required></div>
              <div class="field"><label for="pag-obs">Observação</label>
                <input id="pag-obs" name="observacao" maxlength="255" [(ngModel)]="form.observacao"></div>
            </div>
            <div class="actions"><button class="btn primary" type="submit" [disabled]="enviando()">Registrar pagamento</button></div>
          </form>
        }
      </div>
    }
  `,
})
export class OsPagamentos {
  private api = inject(Api);
  os = input.required<Os>();
  mudou = output<void>();

  situacao = signal<SituacaoPagamento | null>(null);
  erro = signal(''); aviso = signal(''); enviando = signal(false);
  removendo = signal<number | null>(null);
  formas = Object.keys(FORMA_LABEL);
  form = { valor: '', forma: 'pix', pago_em: hojeBrasilia(), observacao: '' };
  hoje = hojeBrasilia;

  ehDono = computed(() => this.api.user()?.role === 'dono');
  cobravel = computed(() => ['pronta', 'entregue'].includes(this.os().status));
  visivel = computed(() => {
    const s = this.situacao();
    return this.ehDono() && s && (this.cobravel() || s.pagamentos.length) ? s : null;
  });
  podeRegistrar = computed(() => this.cobravel() && (this.situacao()?.saldo_centavos ?? 0) > 0);
  dinheiro = reais; data = dataCurta;
  forma = (f: string) => FORMA_LABEL[f] ?? f;

  constructor() {
    // recarrega sempre que a OS muda (o pai recarrega depois de "mudou" ou de mudar o status)
    effect(() => {
      const o = this.os();
      if (this.ehDono()) untracked(() => this.carregar(o.id));
    });
  }

  private aplicar(s: SituacaoPagamento) {
    this.situacao.set(s);
    this.form.valor = s.saldo_centavos > 0 ? paraTexto(s.saldo_centavos) : '';
  }

  async carregar(osId: number) {
    try { this.aplicar(await this.api.get<SituacaoPagamento>(`/api/os/${osId}/pagamentos`)); }
    catch (e) { this.erro.set((e as ApiError).message); }
  }

  async registrar() {
    this.erro.set(''); this.aviso.set('');
    const centavos = paraCentavos(this.form.valor);
    if (Number.isNaN(centavos) || centavos < 1) { this.erro.set('Informe o valor em reais, por exemplo 45,90.'); return; }
    this.enviando.set(true);
    try {
      const s = await this.api.post<SituacaoPagamento>(`/api/os/${this.os().id}/pagamentos`, {
        valor_centavos: centavos, forma: this.form.forma, pago_em: this.form.pago_em || undefined,
        observacao: this.form.observacao.trim() || undefined,
      });
      this.form = { ...this.form, observacao: '', pago_em: hojeBrasilia() };
      this.aplicar(s);
      this.aviso.set('Pagamento registrado.');
      this.mudou.emit();
    } catch (e) { this.erro.set((e as ApiError).message); }
    finally { this.enviando.set(false); }
  }

  async remover(pagamentoId: number) {
    this.erro.set(''); this.aviso.set(''); this.removendo.set(null);
    try {
      this.aplicar(await this.api.delete<SituacaoPagamento>(`/api/os/${this.os().id}/pagamentos/${pagamentoId}`));
      this.aviso.set('Pagamento removido.');
      this.mudou.emit();
    } catch (e) { this.erro.set((e as ApiError).message); }
  }
}
