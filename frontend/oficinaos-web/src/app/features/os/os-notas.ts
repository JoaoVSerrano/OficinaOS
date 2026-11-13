import { Component, effect, inject, input, signal, untracked } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { Api, ApiError, dataHora } from '../../core/api';

export interface NotaOs { id: number; autor_id: number; autor_nome?: string | null; texto: string; criada_em: string | null; }

/** Anotações internas da OS. Só dono e mecânico; o cliente nunca vê (o backend também bloqueia). */
@Component({
  selector: 'app-os-notas',
  imports: [FormsModule],
  template: `
    <div class="card">
      <h2>Anotações internas</h2>
      <p class="small muted">Visíveis só para a equipe da oficina. O cliente não vê estas anotações.</p>
      @if (erro()) { <div class="alert err" role="alert">{{ erro() }}</div> }
      <form (ngSubmit)="adicionar()">
        <div class="field"><label for="nota-texto">Nova anotação</label>
          <textarea id="nota-texto" name="texto" rows="2" maxlength="2000" [(ngModel)]="texto" required></textarea></div>
        <button class="btn" type="submit" [disabled]="ocupado() || !texto.trim()">Adicionar anotação</button>
      </form>
      @if (notas().length === 0) { <p class="muted" style="margin-top:10px">Nenhuma anotação ainda.</p> } @else {
        <ul style="list-style:none;padding:0;margin:12px 0 0">
          @for (n of notas(); track n.id) {
            <li style="padding:8px 0;border-top:1px solid var(--line)">
              <div class="small muted">{{ autor(n) }} · {{ quando(n.criada_em) }}</div>
              <div style="white-space:pre-wrap">{{ n.texto }}</div>
            </li>
          }
        </ul>
      }
    </div>
  `,
})
export class OsNotas {
  private api = inject(Api);
  osId = input.required<number>();
  notas = signal<NotaOs[]>([]);
  erro = signal(''); ocupado = signal(false);
  texto = '';
  quando = dataHora;

  constructor() {
    effect(() => { const id = this.osId(); untracked(() => this.carregar(id)); });
  }

  autor(n: NotaOs): string {
    if (n.autor_id === this.api.user()?.id) return 'Você';
    return n.autor_nome || `Usuário #${n.autor_id}`;
  }

  async carregar(id = this.osId()) {
    try {
      this.notas.set((await this.api.get<{ notas: NotaOs[] }>(`/api/os/${id}/notas`)).notas);
    } catch (e) {
      this.erro.set((e as ApiError).message);
    }
  }

  async adicionar() {
    const texto = this.texto.trim();
    if (!texto) return;
    this.erro.set(''); this.ocupado.set(true);
    try {
      await this.api.post(`/api/os/${this.osId()}/notas`, { texto });
      this.texto = '';
      await this.carregar();
    } catch (e) {
      this.erro.set((e as ApiError).message);
    } finally {
      this.ocupado.set(false);
    }
  }
}
