import { Component, OnInit, computed, inject, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { ActivatedRoute, Router, RouterLink } from '@angular/router';
import { Anexo, Api, ApiError, Os, STATUS_LABEL, dataHora, paraCentavos, reais } from '../core/api';
import { CatalogoPicker, ItemEscolhido } from '../components/catalogo-picker';
import { OsNotas } from '../components/os-notas';
import { OsOrcamento } from '../components/os-orcamento';
import { OsPagamentos } from '../components/os-pagamentos';

interface Acao { destino: string; texto: string; papeis: string[]; primaria?: boolean; perigo?: boolean }
const ACOES: Record<string, Acao[]> = {
  aberta: [{ destino: 'orcamento_aprovado', texto: 'Aprovar orçamento', papeis: ['dono', 'cliente'], primaria: true },
           { destino: 'cancelada', texto: 'Cancelar', papeis: ['dono'], perigo: true }],
  orcamento_aprovado: [{ destino: 'em_servico', texto: 'Iniciar serviço', papeis: ['dono', 'mecanico'], primaria: true },
                       { destino: 'cancelada', texto: 'Cancelar', papeis: ['dono'], perigo: true }],
  em_servico: [{ destino: 'pronta', texto: 'Marcar como pronta', papeis: ['dono', 'mecanico'], primaria: true },
               { destino: 'cancelada', texto: 'Cancelar', papeis: ['dono'], perigo: true }],
  pronta: [{ destino: 'entregue', texto: 'Entregar veículo', papeis: ['dono'], primaria: true },
           { destino: 'cancelada', texto: 'Cancelar', papeis: ['dono'], perigo: true }],
};

@Component({
  selector: 'app-os-detalhe',
  imports: [FormsModule, RouterLink, OsOrcamento, OsNotas, CatalogoPicker, OsPagamentos],
  template: `
    @if (naoEncontrada()) {
      <div class="card empty"><h1>Ordem de serviço não encontrada</h1>
        <p>Ela não existe ou você não tem acesso a ela.</p><a class="btn primary" routerLink="/app/os">Voltar às ordens de serviço</a></div>
    } @else if (os(); as o) {
      <div class="actions" style="justify-content:space-between;margin-bottom:8px">
        <div><a routerLink="/app/os" class="small">← Ordens de serviço</a>
          <h1>Ordem de serviço #{{ o.id }} <span [class]="'badge ' + o.status">{{ rotulo(o.status) }}</span></h1></div>
        <div class="actions">
          @if (podeEditar()) { <a class="btn" [routerLink]="['/app/os', o.id, 'editar']">Editar</a> }
          @if (ehDono() && !confirmando()) { <button class="btn danger" type="button" (click)="confirmando.set(true)">Excluir</button> }
          @if (confirmando()) { <span class="small">Excluir esta ordem de serviço?</span>
            <button class="btn danger sm" type="button" (click)="excluir()">Sim, excluir</button>
            <button class="btn sm" type="button" (click)="confirmando.set(false)">Não</button> }
        </div>
      </div>
      @if (erro()) { <div class="alert err" role="alert">{{ erro() }}
        @if (limite()) { <div style="margin-top:8px"><a class="btn primary sm" routerLink="/app/plano">Assinar Pro</a></div> }</div> }
      @if (aviso()) { <div class="alert ok" role="status">{{ aviso() }}</div> }

      <div class="card">
        <div class="row">
          <div><span class="muted small">Veículo</span><div><strong>{{ o.veiculo?.placa }}</strong> — {{ o.veiculo?.marca }} {{ o.veiculo?.modelo }}</div></div>
          <div><span class="muted small">Cliente</span><div>{{ o.cliente?.nome }}</div></div>
          <div><span class="muted small">Aberta em</span><div>{{ quando(o.criada_em) }}</div></div>
          <div><span class="muted small">Atualizada em</span><div>{{ quando(o.atualizada_em) }}</div></div>
          @if (o.km_entrada !== null) { <div><span class="muted small">Km de entrada</span><div>{{ o.km_entrada.toLocaleString('pt-BR') }} km</div></div> }
          @if (o.veiculo) { <div><span class="muted small">Histórico</span><div><a [routerLink]="['/app/veiculos', o.veiculo.id, 'historico']">Ver histórico do veículo</a></div></div> }
        </div>
        <p style="margin-top:12px"><span class="muted small">Problema / serviço</span><br>{{ o.descricao }}</p>
        @if (acoes().length) {
          <div class="actions">
            @for (a of acoes(); track a.destino) {
              <button class="btn" type="button" [class.primary]="a.primaria" [class.danger]="a.perigo" (click)="mudarStatus(a.destino)">{{ a.texto }}</button>
            }
          </div>
        }
      </div>

      <div class="card">
        <h2>Itens e orçamento</h2>
        @if (!o.itens?.length) { <p class="muted">Nenhum item ainda.</p> } @else {
          <div class="table-wrap"><table>
            <thead><tr><th>Tipo</th><th>Descrição</th><th class="right">Qtd</th><th class="right">Unitário</th><th class="right">Subtotal</th><th></th></tr></thead>
            <tbody>
              @for (i of o.itens; track i.id) {
                <tr><td>{{ i.tipo === 'peca' ? 'Peça' : 'Serviço' }}</td><td>{{ i.descricao }}</td><td class="right">{{ i.quantidade }}</td>
                  <td class="right nowrap">{{ dinheiro(i.valor_unitario_centavos) }}</td><td class="right nowrap">{{ dinheiro(i.subtotal_centavos) }}</td>
                  <td class="right">@if (podeItens()) { <button class="btn sm" type="button" (click)="removerItem(i.id)" [attr.aria-label]="'Remover ' + i.descricao">Remover</button> }</td></tr>
              }
            </tbody>
            <tfoot><tr><th colspan="4" class="right">Total</th><th class="right nowrap" style="font-size:1rem;color:var(--ink)">{{ dinheiro(o.valor_total_centavos) }}</th><th></th></tr></tfoot>
          </table></div>
        }
        @if (podeItens()) {
          <app-catalogo-picker (escolher)="adicionarDoCatalogo($event)" />
          <form (ngSubmit)="adicionarItem()" style="margin-top:12px">
            <div class="row">
              <div><label for="tipo">Tipo</label><select id="tipo" name="tipo" [(ngModel)]="item.tipo"><option value="servico">Serviço</option><option value="peca">Peça</option></select></div>
              <div><label for="idesc">Descrição</label><input id="idesc" name="idesc" [(ngModel)]="item.descricao" required></div>
              <div><label for="iqtd">Quantidade</label><input id="iqtd" name="iqtd" type="number" min="1" [(ngModel)]="item.quantidade" required></div>
              <div><label for="ival">Valor unitário (R$)</label><input id="ival" name="ival" inputmode="decimal" placeholder="0,00" [(ngModel)]="item.valor" required></div>
            </div>
            <button class="btn" type="submit" style="margin-top:10px">Adicionar item</button>
          </form>
        }
      </div>

      <app-os-orcamento [os]="o" (mudou)="carregar()" />
      <app-os-pagamentos [os]="o" (mudou)="carregar()" />
      @if (ehEquipe()) { <app-os-notas [osId]="o.id" /> }

      <div class="card">
        <h2>Fotos e comprovantes</h2>
        @if (anexos().length === 0) { <p class="muted">Nenhum arquivo enviado.</p> }
        <div class="thumbs">
          @for (a of anexos(); track a.id) {
            <figure style="margin:0"><a [href]="a.url" target="_blank" rel="noopener"><img [src]="a.url" [alt]="'Foto ' + a.nome_original" loading="lazy"></a>
              <figcaption class="small muted">{{ a.nome_original }}
                @if (ehDono()) { <button class="btn sm" type="button" (click)="removerAnexo(a.id)">Remover</button> }</figcaption></figure>
          }
        </div>
        @if (podeAnexar()) {
          <div style="margin-top:12px"><label for="arquivo">Enviar foto (PNG, JPEG ou WEBP, até 5 MB)</label>
            <input id="arquivo" type="file" accept="image/png,image/jpeg,image/webp" (change)="enviar($event)"></div>
        }
      </div>
    } @else { <div class="empty">Carregando…</div> }
  `,
})
export class OsDetalhe implements OnInit {
  private api = inject(Api);
  private route = inject(ActivatedRoute);
  private router = inject(Router);
  id = Number(this.route.snapshot.paramMap.get('id'));
  os = signal<Os | null>(null);
  anexos = signal<Anexo[]>([]);
  naoEncontrada = signal(false); erro = signal(''); limite = signal(false); aviso = signal(''); confirmando = signal(false);
  item = { tipo: 'servico', descricao: '', quantidade: 1, valor: '' };
  papel = computed(() => this.api.user()?.role);
  ehDono = computed(() => this.papel() === 'dono');
  editavel = computed(() => !['entregue', 'cancelada'].includes(this.os()?.status ?? ''));
  podeEditar = computed(() => ['dono', 'mecanico'].includes(this.papel() ?? '') && this.editavel());
  podeItens = computed(() => ['dono', 'mecanico'].includes(this.papel() ?? '') && ['aberta', 'orcamento_aprovado', 'em_servico'].includes(this.os()?.status ?? ''));
  podeAnexar = computed(() => ['dono', 'mecanico'].includes(this.papel() ?? '') && this.os()?.status !== 'cancelada');
  ehEquipe = computed(() => ['dono', 'mecanico'].includes(this.papel() ?? ''));
  /** Com orçamento enviado, aprovar é pelo orçamento (o backend recusa a aprovação direta por status). */
  acoes = computed(() => (ACOES[this.os()?.status ?? ''] ?? []).filter((a) => a.papeis.includes(this.papel() ?? '')
    && !(a.destino === 'orcamento_aprovado' && this.os()?.orcamento_status)));
  rotulo = (s: string) => STATUS_LABEL[s] ?? s;
  dinheiro = reais; quando = dataHora;

  async ngOnInit() { await this.carregar(); }

  async carregar() {
    try {
      this.os.set((await this.api.get<{ ordem: Os }>('/api/os/' + this.id)).ordem);
      this.anexos.set((await this.api.get<{ anexos: Anexo[] }>(`/api/os/${this.id}/anexos`)).anexos);
    } catch (e) {
      const err = e as ApiError;
      if (err.status === 404) this.naoEncontrada.set(true); else this.erro.set(err.message);
    }
  }
  private async tentar(fn: () => Promise<unknown>, sucesso = '') {
    this.erro.set(''); this.limite.set(false); this.aviso.set('');
    try { await fn(); if (sucesso) this.aviso.set(sucesso); await this.carregar(); }
    catch (e) { const err = e as ApiError; this.erro.set(err.message); this.limite.set(err.limitePlano); }
  }
  mudarStatus(destino: string) { return this.tentar(() => this.api.post(`/api/os/${this.id}/status`, { status: destino }), 'Status atualizado.'); }
  adicionarItem() {
    const centavos = paraCentavos(this.item.valor);
    if (Number.isNaN(centavos)) { this.erro.set('Informe o valor em reais, por exemplo 45,90.'); return Promise.resolve(); }
    return this.tentar(async () => {
      await this.api.post(`/api/os/${this.id}/itens`, { tipo: this.item.tipo, descricao: this.item.descricao, quantidade: Number(this.item.quantidade), valor_unitario_centavos: centavos });
      this.item = { tipo: this.item.tipo, descricao: '', quantidade: 1, valor: '' };
    });
  }
  adicionarDoCatalogo(i: ItemEscolhido) {
    return this.tentar(() => this.api.post(`/api/os/${this.id}/itens`, { ...i, quantidade: 1 }), 'Item do catálogo adicionado.');
  }
  removerItem(itemId: number) { return this.tentar(() => this.api.delete(`/api/os/${this.id}/itens/${itemId}`)); }
  async excluir() {
    try { await this.api.delete('/api/os/' + this.id); this.router.navigateByUrl('/app/os'); }
    catch (e) { this.erro.set((e as ApiError).message); this.confirmando.set(false); }
  }
  enviar(ev: Event) {
    const input = ev.target as HTMLInputElement;
    const arquivo = input.files?.[0];
    if (!arquivo) return;
    const form = new FormData();
    form.append('arquivo', arquivo);
    input.value = '';
    return this.tentar(() => this.api.post(`/api/os/${this.id}/anexos`, form), 'Arquivo enviado.');
  }
  removerAnexo(anexoId: number) { return this.tentar(() => this.api.delete(`/api/os/${this.id}/anexos/${anexoId}`)); }
}
