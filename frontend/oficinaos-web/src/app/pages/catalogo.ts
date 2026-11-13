import { Component, OnInit, computed, inject, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { ItemCatalogo, TIPO_LABEL, normalizar } from '../components/catalogo-picker';
import { Api, ApiError, paraCentavos, reais } from '../core/api';

type Tipo = ItemCatalogo['tipo'];

/** "120.50" (ponto como separador decimal) vira "120,50" antes de converter; "1.234,56" segue igual. */
function centavosDoTexto(texto: string): number {
  const t = String(texto ?? '').trim();
  return paraCentavos(/^\d+\.\d{1,2}$/.test(t) ? t.replace('.', ',') : t);
}
function textoDosCentavos(centavos: number): string {
  return (centavos / 100).toFixed(2).replace('.', ',');
}

@Component({
  selector: 'app-catalogo',
  imports: [FormsModule],
  template: `
    <h1>Catálogo de serviços e peças</h1>
    <p class="muted">A tabela de preços da oficina. Cadastre aqui os serviços e peças que você usa sempre;
      na ordem de serviço, eles entram em um clique com o valor padrão. Desativar um item não muda as OS antigas.</p>

    @if (erro()) { <div class="alert err" role="alert">{{ erro() }}</div> }
    @if (aviso()) { <div class="alert ok" role="status">{{ aviso() }}</div> }

    @if (ehDono()) {
      <form class="card" (ngSubmit)="criar()">
        <h2>Novo item</h2>
        <div class="row">
          <div><label for="ntipo">Tipo</label>
            <select id="ntipo" name="ntipo" [(ngModel)]="novo.tipo"><option value="servico">Serviço</option><option value="peca">Peça</option></select></div>
          <div><label for="ndesc">Descrição</label><input id="ndesc" name="ndesc" maxlength="255" [(ngModel)]="novo.descricao" required></div>
          <div><label for="nval">Valor (R$)</label><input id="nval" name="nval" inputmode="decimal" placeholder="0,00" [(ngModel)]="novo.valor" required></div>
        </div>
        <button class="btn primary" type="submit" style="margin-top:10px">Cadastrar item</button>
      </form>
    }

    <div class="card">
      <div class="row">
        <div><label for="busca">Buscar</label>
          <input id="busca" name="busca" type="search" placeholder="Descrição do serviço ou peça" [ngModel]="busca()" (ngModelChange)="busca.set($event)"></div>
        <div><label for="ftipo">Tipo</label>
          <select id="ftipo" name="ftipo" [ngModel]="filtroTipo()" (ngModelChange)="filtroTipo.set($event)">
            <option value="">Todos</option><option value="servico">Serviços</option><option value="peca">Peças</option></select></div>
        @if (ehDono()) {
          <div><label class="nowrap" style="margin-top:28px">
            <input type="checkbox" name="inativos" [ngModel]="mostrarInativos()" (ngModelChange)="alternarInativos($event)"> Mostrar inativos</label></div>
        }
      </div>

      @if (carregando()) { <p class="muted">Carregando…</p> }
      @else if (itens().length === 0) {
        <div class="empty">{{ ehDono() ? 'Nenhum item no catálogo ainda. Cadastre o primeiro acima.' : 'Nenhum item no catálogo ainda. Peça ao dono da oficina para cadastrar.' }}</div>
      } @else if (filtrados().length === 0) {
        <div class="empty">Nenhum item encontrado com esse filtro.</div>
      } @else {
        <div class="table-wrap"><table>
          <thead><tr><th>Tipo</th><th>Descrição</th><th class="right">Valor</th><th>Status</th>@if (ehDono()) { <th></th> }</tr></thead>
          <tbody>
            @for (i of filtrados(); track i.id) {
              @if (editando() === i.id) {
                <tr>
                  <td><select [attr.aria-label]="'Tipo de ' + i.descricao" name="etipo" [(ngModel)]="edicao.tipo"><option value="servico">Serviço</option><option value="peca">Peça</option></select></td>
                  <td><input aria-label="Descrição" name="edesc" maxlength="255" [(ngModel)]="edicao.descricao"></td>
                  <td class="right"><input aria-label="Valor em reais" name="eval" inputmode="decimal" style="max-width:120px" [(ngModel)]="edicao.valor"></td>
                  <td>@if (i.ativo) { <span class="badge">Ativo</span> } @else { <span class="badge muted">Inativo</span> }</td>
                  <td class="right nowrap">
                    <button class="btn sm primary" type="button" (click)="salvarEdicao(i)">Salvar</button>
                    <button class="btn sm" type="button" (click)="cancelarEdicao()">Cancelar</button></td>
                </tr>
              } @else {
                <tr>
                  <td>{{ tipoLabel[i.tipo] }}</td><td>{{ i.descricao }}</td><td class="right nowrap">{{ dinheiro(i.valor_centavos) }}</td>
                  <td>@if (i.ativo) { <span class="badge">Ativo</span> } @else { <span class="badge muted">Inativo</span> }</td>
                  @if (ehDono()) {
                    <td class="right nowrap">
                      <button class="btn sm" type="button" (click)="editar(i)" [attr.aria-label]="'Editar ' + i.descricao">Editar</button>
                      @if (i.ativo) {
                        <button class="btn sm danger" type="button" (click)="desativar(i)" [attr.aria-label]="'Desativar ' + i.descricao">Desativar</button>
                      } @else {
                        <button class="btn sm" type="button" (click)="reativar(i)" [attr.aria-label]="'Reativar ' + i.descricao">Reativar</button>
                      }
                    </td>
                  }
                </tr>
              }
            }
          </tbody>
        </table></div>
      }
    </div>
  `,
})
export class Catalogo implements OnInit {
  private api = inject(Api);
  readonly tipoLabel = TIPO_LABEL;
  readonly dinheiro = reais;

  itens = signal<ItemCatalogo[]>([]);
  carregando = signal(true);
  erro = signal(''); aviso = signal('');
  busca = signal(''); filtroTipo = signal<'' | Tipo>(''); mostrarInativos = signal(false);
  editando = signal<number | null>(null);
  ehDono = computed(() => this.api.user()?.role === 'dono');

  novo: { tipo: Tipo; descricao: string; valor: string } = { tipo: 'servico', descricao: '', valor: '' };
  edicao: { tipo: Tipo; descricao: string; valor: string } = { tipo: 'servico', descricao: '', valor: '' };

  filtrados = computed(() => {
    const termo = normalizar(this.busca());
    const tipo = this.filtroTipo();
    return this.itens().filter((i) => (!tipo || i.tipo === tipo) && (!termo || normalizar(i.descricao).includes(termo)));
  });

  async ngOnInit() { await this.carregar(); }

  async carregar() {
    try {
      const params: Record<string, string> = this.ehDono() && this.mostrarInativos() ? { todos: '1' } : {};
      this.itens.set((await this.api.get<{ itens: ItemCatalogo[] }>('/api/catalogo', params)).itens);
    } catch (e) { this.erro.set((e as ApiError).message); }
    finally { this.carregando.set(false); }
  }

  alternarInativos(valor: boolean) { this.mostrarInativos.set(valor); this.carregar(); }

  private async tentar(acao: () => Promise<unknown>, sucesso: string) {
    this.erro.set(''); this.aviso.set('');
    try { await acao(); this.aviso.set(sucesso); await this.carregar(); return true; }
    catch (e) { this.erro.set((e as ApiError).message); return false; }
  }

  async criar() {
    const valor_centavos = centavosDoTexto(this.novo.valor);
    if (Number.isNaN(valor_centavos)) { this.aviso.set(''); this.erro.set('Informe um valor válido, por exemplo 120,00.'); return; }
    const ok = await this.tentar(() => this.api.post('/api/catalogo', {
      tipo: this.novo.tipo, descricao: this.novo.descricao, valor_centavos }), 'Item cadastrado no catálogo.');
    if (ok) this.novo = { tipo: this.novo.tipo, descricao: '', valor: '' };
  }

  editar(i: ItemCatalogo) {
    this.editando.set(i.id);
    this.edicao = { tipo: i.tipo, descricao: i.descricao, valor: textoDosCentavos(i.valor_centavos) };
  }
  cancelarEdicao() { this.editando.set(null); }

  async salvarEdicao(i: ItemCatalogo) {
    const valor_centavos = centavosDoTexto(this.edicao.valor);
    if (Number.isNaN(valor_centavos)) { this.aviso.set(''); this.erro.set('Informe um valor válido, por exemplo 120,00.'); return; }
    const ok = await this.tentar(() => this.api.put('/api/catalogo/' + i.id, {
      tipo: this.edicao.tipo, descricao: this.edicao.descricao, valor_centavos }), 'Item atualizado.');
    if (ok) this.editando.set(null);
  }

  desativar(i: ItemCatalogo) {
    return this.tentar(() => this.api.delete('/api/catalogo/' + i.id), `"${i.descricao}" foi desativado e não aparece mais na OS.`);
  }
  reativar(i: ItemCatalogo) {
    return this.tentar(() => this.api.put('/api/catalogo/' + i.id, { ativo: true }), `"${i.descricao}" foi reativado.`);
  }
}
