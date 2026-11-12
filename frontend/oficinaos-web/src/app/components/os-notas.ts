import { Component, input } from '@angular/core';

/** Slot das anotações internas da OS (Fase 1, agente A). Só dono e mecânico; o cliente nunca vê. */
@Component({ selector: 'app-os-notas', template: `` })
export class OsNotas {
  osId = input.required<number>();
}
