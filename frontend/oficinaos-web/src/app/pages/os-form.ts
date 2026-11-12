import { Component, OnInit, inject, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { ActivatedRoute, Router, RouterLink } from '@angular/router';
import { Api, ApiError, Os, Veiculo } from '../core/api';

@Component({
  selector: 'app-os-form',
  imports: [FormsModule, RouterLink],
  template: `
    <h1>{{ id ? 'Editar ordem de serviço #' + id : 'Abrir ordem de serviço' }}</h1>
    @if (erro()) { <div class="alert err" role="alert">{{ erro() }}
      @if (limite()) { <div style="margin-top:8px"><a class="btn primary sm" routerLink="/app/plano">Assinar Pro</a></div> }</div> }
    <form class="card" (ngSubmit)="salvar()">
      @if (!id) {
        <div class="field"><label for="veiculo">Veículo</label>
          <select id="veiculo" name="veiculo" [(ngModel)]="veiculoId" required>
            <option [ngValue]="null" disabled>Selecione o veículo…</option>
            @for (v of veiculos(); track v.id) { <option [ngValue]="v.id">{{ v.placa }} — {{ v.marca }} {{ v.modelo }}</option> }
          </select>
          @if (veiculos().length === 0) { <span class="small muted">Nenhum veículo cadastrado. @if (ehDono) { <a routerLink="/app/veiculos">Cadastre um veículo</a> } @else { Peça ao dono da oficina para cadastrar. }</span> }
        </div>
      }
      <div class="field"><label for="descricao">Problema ou serviço a fazer</label>
        <textarea id="descricao" name="descricao" [(ngModel)]="descricao" required minlength="3" placeholder="Ex.: barulho na suspensão dianteira"></textarea></div>
      <div class="field"><label for="km">Quilometragem de entrada (km)</label>
        <input id="km" name="km" type="number" min="0" max="2000000" inputmode="numeric" [(ngModel)]="km" placeholder="Ex.: 45210"></div>
      @if (ehDono) {
        <div class="field"><label for="mec">Mecânico responsável</label>
          <select id="mec" name="mec" [(ngModel)]="mecanicoId">
            <option [ngValue]="null">Sem mecânico atribuído</option>
            @for (m of mecanicos(); track m.id) { <option [ngValue]="m.id">{{ m.nome }}</option> }
          </select></div>
      }
      <div class="actions">
        <button class="btn primary" type="submit" [disabled]="salvando()">{{ salvando() ? 'Salvando…' : (id ? 'Salvar alterações' : 'Abrir ordem de serviço') }}</button>
        <a class="btn" [routerLink]="id ? ['/app/os', id] : '/app/os'">Cancelar</a>
      </div>
    </form>
  `,
})
export class OsForm implements OnInit {
  private api = inject(Api);
  private router = inject(Router);
  private route = inject(ActivatedRoute);
  id = Number(this.route.snapshot.paramMap.get('id')) || 0;
  ehDono = this.api.user()?.role === 'dono';
  veiculos = signal<Veiculo[]>([]);
  mecanicos = signal<{ id: number; nome: string }[]>([]);
  veiculoId: number | null = null; descricao = ''; mecanicoId: number | null = null; km: number | null = null;
  erro = signal(''); limite = signal(false); salvando = signal(false);

  async ngOnInit() {
    try {
      if (this.id) {
        const { ordem } = await this.api.get<{ ordem: Os }>('/api/os/' + this.id);
        this.descricao = ordem.descricao; this.mecanicoId = ordem.mecanico_id; this.km = ordem.km_entrada;
      } else {
        this.veiculos.set((await this.api.get<{ veiculos: Veiculo[] }>('/api/veiculos')).veiculos);
      }
      if (this.ehDono) {
        const eq = await this.api.get<{ equipe: { id: number; nome: string; role: string }[] }>('/api/equipe');
        this.mecanicos.set(eq.equipe.filter((u) => u.role === 'mecanico'));
      }
    } catch (e) { this.erro.set((e as ApiError).message); }
  }
  private kmOuNulo(): number | null {
    return this.km === null || (this.km as unknown) === '' ? null : Math.trunc(Number(this.km));
  }
  async salvar() {
    this.erro.set(''); this.limite.set(false); this.salvando.set(true);
    try {
      if (this.id) {
        const corpo: any = { descricao: this.descricao, km_entrada: this.kmOuNulo() };
        if (this.ehDono) corpo.mecanico_id = this.mecanicoId;
        await this.api.put('/api/os/' + this.id, corpo);
        this.router.navigate(['/app/os', this.id]);
      } else {
        const corpo: any = { veiculo_id: this.veiculoId, descricao: this.descricao, km_entrada: this.kmOuNulo() };
        if (this.ehDono && this.mecanicoId) corpo.mecanico_id = this.mecanicoId;
        const r = await this.api.post<{ ordem: Os }>('/api/os', corpo);
        this.router.navigate(['/app/os', r.ordem.id]);
      }
    } catch (e) {
      const err = e as ApiError;
      this.erro.set(err.message); this.limite.set(err.limitePlano);
    } finally { this.salvando.set(false); }
  }
}
