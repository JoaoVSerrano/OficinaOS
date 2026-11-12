import { Component, input, output } from '@angular/core';
import { Os } from '../core/api';

/** Slot dos pagamentos da OS (Fase 1, agente C): registrar e remover pagamentos (dono, OS pronta/entregue). */
@Component({ selector: 'app-os-pagamentos', template: `` })
export class OsPagamentos {
  os = input.required<Os>();
  mudou = output<void>();
}
