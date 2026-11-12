import { Component, input, output } from '@angular/core';
import { Os } from '../core/api';

/** Slot do orçamento na OS (Fase 1, agente A): versões, enviar, aprovar/recusar, link e impressão.
 *  Contrato: recebe a OS; emite `mudou` quando a OS precisa ser recarregada. */
@Component({ selector: 'app-os-orcamento', template: `` })
export class OsOrcamento {
  os = input.required<Os>();
  mudou = output<void>();
}
