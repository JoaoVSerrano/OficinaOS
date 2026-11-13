import { Component, OnInit, computed, inject, output, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { RouterLink } from '@angular/router';
import { Api, reais } from '../core/api';

export interface ItemEscolhido { tipo: 'servico' | 'peca'; descricao: string; valor_unitario_centavos: number }

/** Item do catálogo como vem de GET /api/catalogo. */
export interface ItemCatalogo { id: number; tipo: 'servico' | 'peca'; descricao: string; valor_centavos: number; ativo: boolean }

export const TIPO_LABEL: Record<ItemCatalogo['tipo'], string> = { servico: 'Serviço', peca: 'Peça' };

/** Busca sem diferenciar maiúsculas nem acentos ("oleo" acha "Óleo"). */
export function normalizar(texto: string): string {
  return texto.normalize('NFD').replace(/[̀-ͯ]/g, '').toLowerCase().trim();
}

const MAX_RESULTADOS = 8;

/** Escolher um item da tabela de preços em um clique, dentro da OS.
 *  Contrato: emite `escolher` com o item; a OS chama o POST /api/os/<id>/itens que já existe.
 *  Se o catálogo não carregar, o picker some e a OS continua funcionando. */
@Component({
  selector: 'app-catalogo-picker',
  imports: [FormsModule, RouterLink],
  template: `
    @if (estado() === 'pronto') {
      <div class="field" style="margin-top:12px">
        @if (itens().length === 0) {
          <p class="muted small">Cadastre seus serviços e peças no <a routerLink="/app/catalogo">Catálogo</a> para adicioná-los aqui em um clique.</p>
        } @else {
          <label for="catalogo-busca">Adicionar do catálogo</label>
          <input id="catalogo-busca" name="catalogo-busca" type="search" autocomplete="off"
                 placeholder="Buscar serviço ou peça" [ngModel]="busca()" (ngModelChange)="busca.set($event)">
          @if (resultados().length === 0) {
            <p class="muted small">Nenhum item do catálogo encontrado.</p>
          } @else {
            <div class="actions" style="margin-top:8px">
              @for (i of resultados(); track i.id) {
                <button class="btn sm" type="button" (click)="escolherItem(i)">
                  {{ i.descricao }} — {{ dinheiro(i.valor_centavos) }} ({{ tipoLabel[i.tipo] }})
                </button>
              }
            </div>
          }
        }
      </div>
    }
  `,
})
export class CatalogoPicker implements OnInit {
  private api = inject(Api);
  escolher = output<ItemEscolhido>();

  estado = signal<'carregando' | 'pronto' | 'falhou'>('carregando');
  itens = signal<ItemCatalogo[]>([]);
  busca = signal('');
  readonly tipoLabel = TIPO_LABEL;
  readonly dinheiro = reais;

  resultados = computed(() => {
    const termo = normalizar(this.busca());
    const lista = termo ? this.itens().filter((i) => normalizar(i.descricao).includes(termo)) : this.itens();
    return lista.slice(0, MAX_RESULTADOS);
  });

  async ngOnInit() {
    try {
      this.itens.set((await this.api.get<{ itens: ItemCatalogo[] }>('/api/catalogo')).itens);
      this.estado.set('pronto');
    } catch {
      this.estado.set('falhou');
    }
  }

  escolherItem(i: ItemCatalogo) {
    this.escolher.emit({ tipo: i.tipo, descricao: i.descricao, valor_unitario_centavos: i.valor_centavos });
  }
}
