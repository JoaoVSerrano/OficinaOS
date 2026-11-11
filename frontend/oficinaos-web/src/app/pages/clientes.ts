import { Component, OnInit, computed, inject, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { Api, ApiError, Cliente } from '../core/api';

@Component({
  selector: 'app-clientes',
  imports: [FormsModule],
  template: `
    <h1>Clientes</h1>
    @if (erro()) { <div class="alert err" role="alert">{{ erro() }}</div> }
    @if (ehDono()) {
      <form class="card" (ngSubmit)="salvar()">
        <h2>{{ editando() ? 'Editar cliente' : 'Novo cliente' }}</h2>
        <div class="row">
          <div><label for="nome">Nome</label><input id="nome" name="nome" [(ngModel)]="form.nome" required></div>
          <div><label for="tel">Telefone</label><input id="tel" name="tel" [(ngModel)]="form.telefone"></div>
          <div><label for="email">E-mail</label><input id="email" name="email" type="email" [(ngModel)]="form.email"></div>
        </div>
        <div class="actions" style="margin-top:10px">
          <button class="btn primary" type="submit">{{ editando() ? 'Salvar' : 'Cadastrar cliente' }}</button>
          @if (editando()) { <button class="btn" type="button" (click)="cancelar()">Cancelar</button> }
        </div>
      </form>
    }
    <div class="card">
      @if (clientes().length === 0) { <div class="empty">Nenhum cliente cadastrado.</div> } @else {
        <div class="table-wrap"><table>
          <thead><tr><th>Nome</th><th>Telefone</th><th>E-mail</th><th></th></tr></thead>
          <tbody>
            @for (c of clientes(); track c.id) {
              <tr><td>{{ c.nome }}</td><td>{{ c.telefone }}</td><td>{{ c.email }}</td>
                <td class="right nowrap">@if (ehDono()) {
                  <button class="btn sm" type="button" (click)="editar(c)">Editar</button>
                  <button class="btn sm danger" type="button" (click)="remover(c)">Remover</button> }</td></tr>
            }
          </tbody>
        </table></div>
      }
    </div>
  `,
})
export class Clientes implements OnInit {
  private api = inject(Api);
  clientes = signal<Cliente[]>([]);
  erro = signal(''); editando = signal<number | null>(null);
  ehDono = computed(() => this.api.user()?.role === 'dono');
  form = { nome: '', telefone: '', email: '' };

  async ngOnInit() { await this.carregar(); }
  private async carregar() {
    try { this.clientes.set((await this.api.get<{ clientes: Cliente[] }>('/api/clientes')).clientes); }
    catch (e) { this.erro.set((e as ApiError).message); }
  }
  async salvar() {
    this.erro.set('');
    try {
      const id = this.editando();
      if (id) await this.api.put('/api/clientes/' + id, this.form); else await this.api.post('/api/clientes', this.form);
      this.cancelar(); await this.carregar();
    } catch (e) { this.erro.set((e as ApiError).message); }
  }
  editar(c: Cliente) { this.editando.set(c.id); this.form = { nome: c.nome, telefone: c.telefone ?? '', email: c.email ?? '' }; }
  cancelar() { this.editando.set(null); this.form = { nome: '', telefone: '', email: '' }; }
  async remover(c: Cliente) {
    this.erro.set('');
    try { await this.api.delete('/api/clientes/' + c.id); await this.carregar(); }
    catch (e) { this.erro.set((e as ApiError).message); }
  }
}
