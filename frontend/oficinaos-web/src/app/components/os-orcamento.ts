import { Component, computed, effect, inject, input, output, signal, untracked } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { RouterLink } from '@angular/router';
import { Api, ApiError, Os, dataHora, paraCentavos, reais } from '../core/api';

export type OrcamentoStatus = 'enviado' | 'aprovado' | 'recusado' | 'substituido';

export interface OrcamentoItem {
  tipo: 'servico' | 'peca'; descricao: string; quantidade: number;
  valor_unitario_centavos: number; subtotal_centavos: number;
}

/** Campos comuns à versão vista pela equipe e pelo link público. */
export interface OrcamentoBase {
  versao: number; status: OrcamentoStatus; expirado: boolean; itens: OrcamentoItem[];
  subtotal_centavos: number; desconto_centavos: number; total_centavos: number;
  validade_ate: string; observacoes_cliente: string | null; enviado_em: string | null;
  decidido_em: string | null; motivo_recusa: string | null;
}

export interface Orcamento extends OrcamentoBase { id: number; decidido_via: 'app' | 'link' | null; }

export const ORC_STATUS_LABEL: Record<OrcamentoStatus, string> = {
  enviado: 'Aguardando o cliente', aprovado: 'Aprovado', recusado: 'Recusado', substituido: 'Substituído',
};

/** "2026-11-20" -> "20/11/2026" (sem passar por Date, para não deslocar o dia pelo fuso). */
export function dataCurta(iso: string | null | undefined): string {
  if (!iso) return '';
  const [a, m, d] = iso.slice(0, 10).split('-');
  return `${d}/${m}/${a}`;
}

/** Orçamento da OS: versões, enviar (dono), aprovar/recusar (dono e cliente), link e impressão. */
@Component({
  selector: 'app-os-orcamento',
  imports: [FormsModule, RouterLink],
  template: `
    @if (visivel()) {
      <div class="card">
        <div class="actions" style="justify-content:space-between">
          <h2>Orçamento</h2>
          @if (atual()) { <a class="btn sm" [routerLink]="['/app/os', os().id, 'orcamento']">Ver / imprimir orçamento</a> }
        </div>
        @if (erro()) { <div class="alert err" role="alert">{{ erro() }}</div> }
        @if (aviso()) { <div class="alert ok" role="status">{{ aviso() }}</div> }

        @if (atual(); as v) {
          <div class="row">
            <div><span class="muted small">Versão {{ v.versao }}</span>
              <div><span [class]="'badge ' + v.status">{{ rotulo(v.status) }}</span>
                @if (v.expirado) { <span class="badge cancelada">Expirado</span> }</div></div>
            <div><span class="muted small">Total</span><div><strong>{{ dinheiro(v.total_centavos) }}</strong></div></div>
            @if (v.desconto_centavos) { <div><span class="muted small">Desconto</span><div>{{ dinheiro(v.desconto_centavos) }}</div></div> }
            <div><span class="muted small">Válido até</span><div>{{ dia(v.validade_ate) }}</div></div>
            @if (v.decidido_em) { <div><span class="muted small">Decidido em</span>
              <div>{{ quando(v.decidido_em) }} {{ v.decidido_via === 'link' ? '(pelo link)' : '(pelo app)' }}</div></div> }
          </div>
          @if (v.motivo_recusa) { <p style="margin-top:8px"><span class="muted small">Motivo da recusa</span><br>{{ v.motivo_recusa }}</p> }
          @if (desatualizado()) {
            <div class="alert warn" style="margin-top:8px">Os itens mudaram depois do envio: envie uma nova versão ao cliente.</div>
          }

          @if (podeDecidir()) {
            <div class="actions" style="margin-top:12px">
              <button class="btn primary" type="button" [disabled]="ocupado()" (click)="decidir('aprovar')">Aprovar orçamento</button>
              @if (!recusando()) { <button class="btn danger" type="button" (click)="recusando.set(true)">Recusar</button> }
            </div>
            @if (recusando()) {
              <form (ngSubmit)="decidir('recusar')" style="margin-top:10px">
                <div class="field"><label for="orc-motivo">Motivo da recusa</label>
                  <textarea id="orc-motivo" name="motivo" rows="2" maxlength="500" [(ngModel)]="motivo" required></textarea></div>
                <div class="actions">
                  <button class="btn danger" type="submit" [disabled]="ocupado()">Confirmar recusa</button>
                  <button class="btn" type="button" (click)="recusando.set(false)">Voltar</button>
                </div>
              </form>
            }
          }
        } @else { <p class="muted">Nenhum orçamento enviado ao cliente ainda.</p> }

        @if (link()) {
          <div class="alert info" style="margin-top:12px">
            <strong>Link do orçamento para o cliente</strong>
            <p class="small">Copie agora: por segurança, o link aparece só neste momento.</p>
            <div class="actions">
              <input [value]="link()" readonly aria-label="Link do orçamento" style="flex:1;min-width:200px" (focus)="$any($event.target).select()">
              <button class="btn sm" type="button" (click)="copiar()">{{ copiado() ? 'Copiado!' : 'Copiar' }}</button>
              <a class="btn sm" [href]="whatsapp()" target="_blank" rel="noopener">Enviar por WhatsApp</a>
            </div>
          </div>
        }

        @if (podeEnviar()) {
          <form (ngSubmit)="enviar()" style="margin-top:12px">
            <h3>{{ atual() ? 'Enviar nova versão ao cliente' : 'Enviar orçamento ao cliente' }}</h3>
            <p class="small muted">Subtotal atual dos itens: {{ dinheiro(os().valor_total_centavos) }}</p>
            <div class="row">
              <div><label for="orc-desc">Desconto (R$)</label>
                <input id="orc-desc" name="desconto" inputmode="decimal" placeholder="0,00" [(ngModel)]="form.desconto"></div>
              <div><label for="orc-val">Validade (dias)</label>
                <input id="orc-val" name="validade" type="number" min="1" max="90" [(ngModel)]="form.validade" required></div>
            </div>
            <div class="field"><label for="orc-obs">Observações para o cliente</label>
              <textarea id="orc-obs" name="obs" rows="2" maxlength="2000" [(ngModel)]="form.observacoes"></textarea></div>
            <button class="btn primary" type="submit" [disabled]="ocupado() || os().valor_total_centavos <= 0">Enviar orçamento ao cliente</button>
            @if (os().valor_total_centavos <= 0) { <span class="small muted"> Adicione itens com valor antes de enviar.</span> }
          </form>
        }

        @if (historico().length) {
          <details style="margin-top:12px"><summary class="small">Versões anteriores ({{ historico().length }})</summary>
            <ul class="small" style="margin:6px 0 0;padding-left:18px">
              @for (h of historico(); track h.id) {
                <li>v{{ h.versao }} — {{ rotulo(h.status) }} — {{ dinheiro(h.total_centavos) }} — enviado em {{ quando(h.enviado_em) }}
                  @if (h.motivo_recusa) { — motivo: {{ h.motivo_recusa }} }</li>
              }
            </ul>
          </details>
        }
      </div>
    }
  `,
})
export class OsOrcamento {
  private api = inject(Api);
  os = input.required<Os>();
  mudou = output<void>();

  versoes = signal<Orcamento[]>([]);
  carregado = signal(false);
  erro = signal(''); aviso = signal(''); ocupado = signal(false);
  recusando = signal(false); copiado = signal(false);
  link = signal('');
  motivo = '';
  form = { desconto: '', validade: 7, observacoes: '' };

  papel = computed(() => this.api.user()?.role);
  ehDono = computed(() => this.papel() === 'dono');
  atual = computed(() => this.versoes()[0] ?? null);
  historico = computed(() => this.versoes().slice(1));
  visivel = computed(() => this.carregado() && (this.ehDono() || this.versoes().length > 0));
  podeEnviar = computed(() => this.ehDono() && this.os().status === 'aberta');
  podeDecidir = computed(() => {
    const v = this.atual();
    return !!v && v.status === 'enviado' && !v.expirado && this.os().status === 'aberta'
      && (this.papel() === 'dono' || this.papel() === 'cliente');
  });
  desatualizado = computed(() => {
    const v = this.atual();
    return !!v && v.status === 'enviado' && this.ehDono() && v.subtotal_centavos !== this.os().valor_total_centavos;
  });

  rotulo = (s: OrcamentoStatus) => ORC_STATUS_LABEL[s] ?? s;
  dinheiro = reais; quando = dataHora; dia = dataCurta;

  constructor() {
    // recarrega quando a OS muda (o pai recarrega a OS depois de itens, status etc.)
    effect(() => {
      const o = this.os();
      void o.valor_total_centavos; void o.status; void o.orcamento_status;
      untracked(() => this.carregar(o.id));
    });
  }

  async carregar(id = this.os().id) {
    try {
      const r = await this.api.get<{ orcamentos: Orcamento[] }>(`/api/os/${id}/orcamentos`);
      this.versoes.set(r.orcamentos);
    } catch (e) {
      this.versoes.set([]);
      this.erro.set((e as ApiError).message);
    } finally {
      this.carregado.set(true);
    }
  }

  async enviar() {
    this.erro.set(''); this.aviso.set('');
    const desconto = this.form.desconto.trim() ? paraCentavos(this.form.desconto) : 0;
    if (Number.isNaN(desconto)) { this.erro.set('Desconto inválido.'); return; }
    const validade = Number(this.form.validade);
    if (!Number.isInteger(validade) || validade < 1 || validade > 90) { this.erro.set('Validade de 1 a 90 dias.'); return; }
    this.ocupado.set(true);
    try {
      const r = await this.api.post<{ orcamento: Orcamento; link: string }>(`/api/os/${this.os().id}/orcamentos`, {
        desconto_centavos: desconto, validade_dias: validade, observacoes_cliente: this.form.observacoes,
      });
      this.link.set(location.origin + r.link);
      this.copiado.set(false);
      this.aviso.set(`Orçamento v${r.orcamento.versao} enviado. Compartilhe o link com o cliente.`);
      this.form = { desconto: '', validade: 7, observacoes: '' };
      await this.carregar();
      this.mudou.emit();
    } catch (e) {
      this.erro.set((e as ApiError).message);
    } finally {
      this.ocupado.set(false);
    }
  }

  async decidir(acao: 'aprovar' | 'recusar') {
    const v = this.atual();
    if (!v) return;
    this.erro.set(''); this.aviso.set('');
    if (acao === 'recusar' && this.motivo.trim().length < 3) { this.erro.set('Informe o motivo da recusa (mínimo 3 caracteres).'); return; }
    this.ocupado.set(true);
    try {
      await this.api.post(`/api/os/${this.os().id}/orcamentos/${v.id}/decisao`,
        acao === 'aprovar' ? { acao } : { acao, motivo: this.motivo.trim() });
      this.aviso.set(acao === 'aprovar' ? 'Orçamento aprovado.' : 'Orçamento recusado. A oficina vai ajustar e enviar uma nova versão.');
      this.recusando.set(false); this.motivo = '';
      await this.carregar();
      this.mudou.emit();
    } catch (e) {
      this.erro.set((e as ApiError).message);
      await this.carregar();
    } finally {
      this.ocupado.set(false);
    }
  }

  whatsapp(): string {
    const texto = `Olá! Segue o orçamento da OS #${this.os().id} para aprovação: ${this.link()}`;
    return 'https://wa.me/?text=' + encodeURIComponent(texto);
  }

  async copiar() {
    try {
      await navigator.clipboard.writeText(this.link());
      this.copiado.set(true);
    } catch {
      this.erro.set('Não foi possível copiar automaticamente. Selecione o link e copie.');
    }
  }
}
