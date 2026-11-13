import { RouterLink } from '@angular/router';
import { Component, OnInit, computed, inject, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { Api, ApiError, Cliente, Veiculo } from '../../core/api';

@Component({
  selector: 'app-veiculos',
  imports: [FormsModule, RouterLink],
  template: `
    <h1>Veículos</h1>
    @if (erro()) { <div class="alert err" role="alert">{{ erro() }}</div> }
    @if (ehDono()) {
      <form class="card" (ngSubmit)="salvar()">
        <h2>{{ editando() ? 'Editar veículo' : 'Novo veículo' }}</h2>
        <div class="row">
          <div><label for="cli">Cliente</label>
            <select id="cli" name="cli" [(ngModel)]="form.cliente_id" required [disabled]="!!editando()">
              <option [ngValue]="null" disabled>Selecione…</option>
              @for (c of clientes(); track c.id) { <option [ngValue]="c.id">{{ c.nome }}</option> }
            </select></div>
          <div><label for="placa">Placa</label><input id="placa" name="placa" [(ngModel)]="form.placa" maxlength="8" placeholder="ABC1D23" required></div>
          <div><label for="marca">Marca</label><input id="marca" name="marca" [(ngModel)]="form.marca" required></div>
          <div><label for="modelo">Modelo</label><input id="modelo" name="modelo" [(ngModel)]="form.modelo" required></div>
          <div><label for="ano">Ano</label><input id="ano" name="ano" type="number" [(ngModel)]="form.ano"></div>
        </div>
        @if (clientes().length === 0) { <p class="small muted" style="margin-top:8px">Cadastre um cliente antes de cadastrar o veículo.</p> }
        <div class="actions" style="margin-top:10px">
          <button class="btn primary" type="submit">{{ editando() ? 'Salvar' : 'Cadastrar veículo' }}</button>
          @if (editando()) { <button class="btn" type="button" (click)="cancelar()">Cancelar</button> }
        </div>
      </form>
    }
    <div class="card">
      @if (veiculos().length === 0) { <div class="empty">Nenhum veículo cadastrado.</div> } @else {
        <div class="table-wrap"><table>
          <thead><tr><th>Placa</th><th>Veículo</th><th>Ano</th><th>Cliente</th><th></th></tr></thead>
          <tbody>
            @for (v of veiculos(); track v.id) {
              <tr><td><strong>{{ v.placa }}</strong></td><td>{{ v.marca }} {{ v.modelo }}</td><td>{{ v.ano }}</td><td>{{ nomeCliente(v.cliente_id) }}</td>
                <td class="right nowrap"><a class="btn sm" [routerLink]="['/app/veiculos', v.id, 'historico']">Histórico</a>
                  @if (ehDono()) {
                  <button class="btn sm" type="button" (click)="editar(v)">Editar</button>
                  <button class="btn sm danger" type="button" (click)="remover(v)">Remover</button> }</td></tr>
            }
          </tbody>
        </table></div>
      }
    </div>
  `,
})
export class Veiculos implements OnInit {
  private api = inject(Api);
  veiculos = signal<Veiculo[]>([]);
  clientes = signal<Cliente[]>([]);
  erro = signal(''); editando = signal<number | null>(null);
  ehDono = computed(() => this.api.user()?.role === 'dono');
  form: { cliente_id: number | null; placa: string; marca: string; modelo: string; ano: number | null } = this.vazio();

  private vazio() { return { cliente_id: null, placa: '', marca: '', modelo: '', ano: null }; }
  async ngOnInit() { await this.carregar(); }
  private async carregar() {
    try {
      this.veiculos.set((await this.api.get<{ veiculos: Veiculo[] }>('/api/veiculos')).veiculos);
      if (['dono', 'mecanico'].includes(this.api.user()?.role ?? ''))
        this.clientes.set((await this.api.get<{ clientes: Cliente[] }>('/api/clientes')).clientes);
    } catch (e) { this.erro.set((e as ApiError).message); }
  }
  nomeCliente(id: number) { return this.clientes().find((c) => c.id === id)?.nome ?? ''; }
  async salvar() {
    this.erro.set('');
    try {
      const id = this.editando();
      if (id) await this.api.put('/api/veiculos/' + id, this.form); else await this.api.post('/api/veiculos', this.form);
      this.cancelar(); await this.carregar();
    } catch (e) { this.erro.set((e as ApiError).message); }
  }
  editar(v: Veiculo) { this.editando.set(v.id); this.form = { cliente_id: v.cliente_id, placa: v.placa, marca: v.marca, modelo: v.modelo, ano: v.ano }; }
  cancelar() { this.editando.set(null); this.form = this.vazio(); }
  async remover(v: Veiculo) {
    this.erro.set('');
    try { await this.api.delete('/api/veiculos/' + v.id); await this.carregar(); }
    catch (e) { this.erro.set((e as ApiError).message); }
  }
}
