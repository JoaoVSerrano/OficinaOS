import { Component, output } from '@angular/core';

export interface ItemEscolhido { tipo: 'servico' | 'peca'; descricao: string; valor_unitario_centavos: number }

/** Slot do catálogo na OS (Fase 1, agente B): escolher um item da tabela de preços em um clique.
 *  Contrato: emite `escolher` com o item; a OS chama o POST /api/os/<id>/itens que já existe. */
@Component({ selector: 'app-catalogo-picker', template: `` })
export class CatalogoPicker {
  escolher = output<ItemEscolhido>();
}
