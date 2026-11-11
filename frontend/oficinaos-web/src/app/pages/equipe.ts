import { Component, OnInit, inject, signal } from '@angular/core';
import { Api, ApiError, PAPEL_LABEL } from '../core/api';

@Component({
  selector: 'app-equipe',
  template: `
    <h1>Equipe</h1>
    @if (erro()) { <div class="alert err" role="alert">{{ erro() }}</div> }
    <div class="card">
      <h2>Código de convite</h2>
      <p class="muted">Passe este código a mecânicos e clientes: eles o informam ao criar a conta e entram na sua oficina.</p>
      <div class="actions"><code style="font-size:1.4rem;font-weight:800;letter-spacing:.08em" aria-label="Código de convite">{{ codigo() }}</code>
        <button class="btn sm" type="button" (click)="copiar()">{{ copiado() ? 'Copiado!' : 'Copiar' }}</button></div>
      <p class="small muted" style="margin-top:8px">Plano atual: <strong>{{ plano() }}</strong></p>
    </div>
    <div class="card">
      <h2>Pessoas da oficina</h2>
      <div class="table-wrap"><table>
        <thead><tr><th>Nome</th><th>E-mail</th><th>Papel</th></tr></thead>
        <tbody>@for (p of equipe(); track p.id) { <tr><td>{{ p.nome }}</td><td>{{ p.email }}</td><td>{{ rotulo(p.role) }}</td></tr> }</tbody>
      </table></div>
    </div>
  `,
})
export class Equipe implements OnInit {
  private api = inject(Api);
  codigo = signal(''); plano = signal(''); copiado = signal(false); erro = signal('');
  equipe = signal<{ id: number; nome: string; email: string; role: string }[]>([]);
  rotulo = (r: string) => PAPEL_LABEL[r] ?? r;

  async ngOnInit() {
    try {
      const o = await this.api.get<{ oficina: { codigo_convite: string; plano: string } }>('/api/oficina');
      this.codigo.set(o.oficina.codigo_convite); this.plano.set(o.oficina.plano === 'pro' ? 'Pro' : 'Free');
      this.equipe.set((await this.api.get<{ equipe: any[] }>('/api/equipe')).equipe);
    } catch (e) { this.erro.set((e as ApiError).message); }
  }
  async copiar() {
    try { await navigator.clipboard.writeText(this.codigo()); this.copiado.set(true); setTimeout(() => this.copiado.set(false), 2000); } catch { /* sem permissão */ }
  }
}
