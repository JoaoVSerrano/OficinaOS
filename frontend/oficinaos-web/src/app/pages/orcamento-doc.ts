import { Component, OnInit, ViewEncapsulation, computed, inject, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { ActivatedRoute, RouterLink } from '@angular/router';
import { Api, ApiError, Os, dataHora, reais } from '../core/api';
import { ORC_STATUS_LABEL, Orcamento, OrcamentoBase, OrcamentoStatus, dataCurta } from '../components/os-orcamento';

/** Resposta de GET /api/publico/orcamentos/:token (sem ids nem contato). */
interface OrcamentoPublico {
  oficina: { nome: string };
  cliente: { nome: string };
  veiculo: { placa: string; marca: string; modelo: string; ano: number | null };
  os: { descricao: string; km_entrada: number | null };
  orcamento: OrcamentoBase;
}

/** Dados do documento, montados no modo público (token) ou no modo interno (OS #id). */
interface Documento {
  titulo: string; cliente: string; veiculo: string; km: number | null; descricao: string; orc: OrcamentoBase;
}

/**
 * Documento do orçamento para ver/imprimir.
 * - /orcamento/:token (público, sem login): o cliente aprova ou recusa pelo link.
 * - /app/os/:id/orcamento (dentro do app): versão mais recente da OS, para imprimir / salvar PDF.
 */
@Component({
  selector: 'app-orcamento-doc',
  imports: [FormsModule, RouterLink],
  encapsulation: ViewEncapsulation.None,
  styles: [`
    app-orcamento-doc { display: block; }
    app-orcamento-doc .doc-pagina { max-width: 860px; margin: 0 auto; padding: 16px; }
    app-orcamento-doc .doc { background: var(--card, #fff); border: 1px solid var(--line, #ddd); border-radius: 10px; padding: 24px; }
    app-orcamento-doc .doc-cab { display: flex; justify-content: space-between; gap: 12px; flex-wrap: wrap;
      border-bottom: 2px solid var(--line, #ddd); padding-bottom: 12px; margin-bottom: 16px; }
    app-orcamento-doc .doc-cab h1 { margin: 0; }
    app-orcamento-doc .doc-dados { display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap: 10px; margin-bottom: 16px; }
    app-orcamento-doc .doc table { width: 100%; border-collapse: collapse; }
    app-orcamento-doc .doc th, app-orcamento-doc .doc td { padding: 6px 8px; border-bottom: 1px solid var(--line, #ddd); text-align: left; }
    app-orcamento-doc .doc .right { text-align: right; }
    app-orcamento-doc .doc-totais { margin-left: auto; margin-top: 12px; min-width: 260px; max-width: 320px; }
    app-orcamento-doc .doc-totais div { display: flex; justify-content: space-between; padding: 3px 0; }
    app-orcamento-doc .doc-totais .doc-total { font-size: 1.15rem; font-weight: 700; border-top: 2px solid var(--line, #ddd); padding-top: 6px; }
    app-orcamento-doc .doc-decisao { margin-top: 16px; }
    @media print {
      app-shell header, .no-print { display: none !important; }
      app-orcamento-doc .doc-pagina { padding: 0; max-width: none; }
      app-orcamento-doc .doc { border: none; padding: 0; }
      body { background: #fff !important; }
    }
  `],
  template: `
    <div class="doc-pagina">
      @if (carregando()) { <div class="empty">Carregando…</div> }
      @else if (invalido()) {
        <div class="card empty"><h1>Link inválido</h1>
          <p>Este link de orçamento não existe ou não está mais disponível. Peça um link novo à oficina.</p></div>
      } @else if (doc(); as d) {
        <div class="actions no-print" style="justify-content:space-between;margin-bottom:10px">
          @if (!publico) { <a class="small" [routerLink]="['/app/os', id]">← Voltar à ordem de serviço</a> } @else { <span></span> }
          <button class="btn" type="button" (click)="imprimir()">Imprimir / salvar PDF</button>
        </div>

        @if (erro()) { <div class="alert err no-print" role="alert">{{ erro() }}</div> }
        @if (resultado()) { <div class="alert ok no-print" role="status">{{ resultado() }}</div> }
        @if (publico) {
          @switch (situacao()) {
            @case ('substituido') { <div class="alert warn no-print">Este orçamento foi substituído por uma versão mais nova. Peça o link novo à oficina.</div> }
            @case ('expirado') { <div class="alert warn no-print">Este orçamento expirou em {{ dia(d.orc.validade_ate) }}. Peça um orçamento atualizado à oficina.</div> }
            @case ('aprovado') { @if (!resultado()) { <div class="alert ok no-print">Este orçamento já foi aprovado em {{ quando(d.orc.decidido_em) }}.</div> } }
            @case ('recusado') { @if (!resultado()) { <div class="alert info no-print">Este orçamento foi recusado em {{ quando(d.orc.decidido_em) }}.</div> } }
          }
        }

        <article class="doc">
          <div class="doc-cab">
            <div><h1>{{ d.titulo }}</h1><div class="muted">Orçamento — versão {{ d.orc.versao }}</div></div>
            <div class="right">
              <span [class]="'badge ' + d.orc.status">{{ rotulo(d.orc.status) }}</span>
              @if (d.orc.expirado) { <span class="badge cancelada">Expirado</span> }
              <div class="small muted" style="margin-top:4px">Enviado em {{ quando(d.orc.enviado_em) }}</div>
              <div class="small">Válido até <strong>{{ dia(d.orc.validade_ate) }}</strong></div>
            </div>
          </div>

          <div class="doc-dados">
            <div><span class="muted small">Cliente</span><div>{{ d.cliente }}</div></div>
            <div><span class="muted small">Veículo</span><div>{{ d.veiculo }}</div></div>
            @if (d.km !== null) { <div><span class="muted small">Km de entrada</span><div>{{ d.km.toLocaleString('pt-BR') }} km</div></div> }
          </div>
          <p><span class="muted small">Problema / serviço</span><br>{{ d.descricao }}</p>

          <div class="table-wrap"><table>
            <thead><tr><th>Tipo</th><th>Descrição</th><th class="right">Qtd</th><th class="right">Unitário</th><th class="right">Subtotal</th></tr></thead>
            <tbody>
              @for (i of d.orc.itens; track $index) {
                <tr><td>{{ i.tipo === 'peca' ? 'Peça' : 'Serviço' }}</td><td>{{ i.descricao }}</td><td class="right">{{ i.quantidade }}</td>
                  <td class="right nowrap">{{ dinheiro(i.valor_unitario_centavos) }}</td><td class="right nowrap">{{ dinheiro(i.subtotal_centavos) }}</td></tr>
              }
            </tbody>
          </table></div>

          <div class="doc-totais">
            <div><span>Subtotal</span><span>{{ dinheiro(d.orc.subtotal_centavos) }}</span></div>
            @if (d.orc.desconto_centavos) { <div><span>Desconto</span><span>− {{ dinheiro(d.orc.desconto_centavos) }}</span></div> }
            <div class="doc-total"><span>Total</span><span>{{ dinheiro(d.orc.total_centavos) }}</span></div>
          </div>

          @if (d.orc.observacoes_cliente) {
            <p style="margin-top:16px"><span class="muted small">Observações</span><br><span style="white-space:pre-wrap">{{ d.orc.observacoes_cliente }}</span></p>
          }
          @if (d.orc.motivo_recusa) { <p><span class="muted small">Motivo da recusa</span><br>{{ d.orc.motivo_recusa }}</p> }
        </article>

        @if (publico && situacao() === 'pendente') {
          <div class="card doc-decisao no-print">
            <h2>Sua decisão</h2>
            <div class="actions">
              <button class="btn primary" type="button" [disabled]="ocupado()" (click)="decidir('aprovar')">Aprovar orçamento</button>
              @if (!recusando()) { <button class="btn danger" type="button" (click)="recusando.set(true)">Recusar</button> }
            </div>
            @if (recusando()) {
              <form (ngSubmit)="decidir('recusar')" style="margin-top:10px">
                <div class="field"><label for="doc-motivo">Por que você está recusando? (obrigatório)</label>
                  <textarea id="doc-motivo" name="motivo" rows="3" maxlength="500" [(ngModel)]="motivo" required></textarea></div>
                <div class="actions">
                  <button class="btn danger" type="submit" [disabled]="ocupado() || motivo.trim().length < 3">Confirmar recusa</button>
                  <button class="btn" type="button" (click)="recusando.set(false)">Voltar</button>
                </div>
              </form>
            }
          </div>
        }
      } @else if (erro()) { <div class="alert err" role="alert">{{ erro() }}</div> }
      @else { <div class="card empty"><p>Esta ordem de serviço ainda não tem orçamento enviado.</p>
        <a class="btn" [routerLink]="['/app/os', id]">Voltar à ordem de serviço</a></div> }
    </div>
  `,
})
export class OrcamentoDoc implements OnInit {
  private api = inject(Api);
  private route = inject(ActivatedRoute);
  token = this.route.snapshot.paramMap.get('token');
  id = Number(this.route.snapshot.paramMap.get('id'));
  publico = !!this.token;

  doc = signal<Documento | null>(null);
  carregando = signal(true); invalido = signal(false); ocupado = signal(false); recusando = signal(false);
  erro = signal(''); resultado = signal('');
  motivo = '';

  situacao = computed<'pendente' | 'expirado' | OrcamentoStatus | null>(() => {
    const o = this.doc()?.orc;
    if (!o) return null;
    if (o.status === 'enviado') return o.expirado ? 'expirado' : 'pendente';
    return o.status;
  });

  rotulo = (s: OrcamentoStatus) => ORC_STATUS_LABEL[s] ?? s;
  dinheiro = reais; quando = dataHora; dia = dataCurta;

  async ngOnInit() {
    try {
      if (this.publico) await this.carregarPublico();
      else await this.carregarInterno();
    } finally {
      this.carregando.set(false);
    }
  }

  private url() { return `/api/publico/orcamentos/${encodeURIComponent(this.token ?? '')}`; }

  private dePublico(p: OrcamentoPublico): Documento {
    const v = p.veiculo;
    return {
      titulo: p.oficina.nome, cliente: p.cliente.nome, km: p.os.km_entrada, descricao: p.os.descricao,
      veiculo: `${v.placa} — ${v.marca} ${v.modelo}${v.ano ? ' ' + v.ano : ''}`, orc: p.orcamento,
    };
  }

  private async carregarPublico() {
    try {
      this.doc.set(this.dePublico(await this.api.get<OrcamentoPublico>(this.url())));
    } catch (e) {
      const err = e as ApiError;
      if (err.status === 404) this.invalido.set(true);
      else this.erro.set(err.message);
    }
  }

  private async carregarInterno() {
    try {
      const [os, versoes] = await Promise.all([
        this.api.get<{ ordem: Os }>(`/api/os/${this.id}`),
        this.api.get<{ orcamentos: Orcamento[] }>(`/api/os/${this.id}/orcamentos`),
      ]);
      const o = os.ordem;
      const atual = versoes.orcamentos[0];
      if (!atual) return;
      this.doc.set({
        titulo: `OS #${o.id}`, cliente: o.cliente?.nome ?? '', km: o.km_entrada, descricao: o.descricao,
        veiculo: o.veiculo ? `${o.veiculo.placa} — ${o.veiculo.marca} ${o.veiculo.modelo}` : '', orc: atual,
      });
    } catch (e) {
      this.erro.set((e as ApiError).message);
    }
  }

  async decidir(acao: 'aprovar' | 'recusar') {
    this.erro.set('');
    const motivo = this.motivo.trim();
    if (acao === 'recusar' && motivo.length < 3) { this.erro.set('Informe o motivo da recusa (mínimo 3 caracteres).'); return; }
    this.ocupado.set(true);
    try {
      const r = await this.api.post<OrcamentoPublico>(`${this.url()}/decisao`, acao === 'aprovar' ? { acao } : { acao, motivo });
      this.doc.set(this.dePublico(r));
      this.recusando.set(false);
      this.resultado.set(acao === 'aprovar'
        ? 'Orçamento aprovado! A oficina já foi avisada e vai iniciar o serviço.'
        : 'Orçamento recusado. A oficina vai entrar em contato com uma nova proposta.');
    } catch (e) {
      const err = e as ApiError;
      this.erro.set(err.status === 429 ? 'Muitas tentativas. Aguarde um minuto e tente de novo.' : err.message);
      if ([409, 410].includes(err.status)) await this.carregarPublico();
    } finally {
      this.ocupado.set(false);
    }
  }

  imprimir() { window.print(); }
}
