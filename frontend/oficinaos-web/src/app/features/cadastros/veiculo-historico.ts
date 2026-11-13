import { Component, OnInit, computed, inject, signal } from '@angular/core';
import { ActivatedRoute, RouterLink } from '@angular/router';
import { Api, ApiError, STATUS_LABEL, dataHora, reais } from '../../core/api';

interface OsHistorico {
  id: number; status: string; descricao: string; km_entrada: number | null; criada_em: string;
  entregue_em: string | null; valor_total_centavos: number;
  /** só para o dono */
  valor_devido_centavos?: number; pago_centavos?: number;
}
interface Historico {
  veiculo: { placa: string; marca: string; modelo: string; ano: number | null };
  ultimo_km: number | null; ordens: OsHistorico[];
}

@Component({
  selector: 'app-veiculo-historico',
  imports: [RouterLink],
  template: `
    <a routerLink="/app/veiculos" class="small">← Veículos</a>
    @if (naoEncontrado()) {
      <div class="card empty"><h1>Veículo não encontrado</h1>
        <p>Ele não existe ou você não tem acesso a ele.</p>
        <a class="btn primary" routerLink="/app/veiculos">Voltar aos veículos</a></div>
    } @else if (erro()) {
      <div class="alert err" role="alert">{{ erro() }}</div>
    } @else if (dados(); as d) {
      <h1>Histórico — {{ d.veiculo.placa }}</h1>
      <div class="card">
        <div class="row">
          <div><span class="muted small">Veículo</span><div><strong>{{ d.veiculo.placa }}</strong> — {{ d.veiculo.marca }} {{ d.veiculo.modelo }}</div></div>
          <div><span class="muted small">Ano</span><div>{{ d.veiculo.ano ?? '—' }}</div></div>
          <div><span class="muted small">Último km informado</span><div>{{ d.ultimo_km !== null ? km(d.ultimo_km) : '—' }}</div></div>
          <div><span class="muted small">Ordens de serviço</span><div>{{ d.ordens.length }}</div></div>
        </div>
      </div>

      @if (!d.ordens.length) {
        <div class="card empty"><p class="muted">Nenhuma ordem de serviço para este veículo ainda.</p></div>
      } @else {
        <div class="card"><div class="table-wrap"><table>
          <thead><tr><th>Data</th><th class="right">Km</th><th>Descrição</th><th>Status</th><th class="right">Total</th>
            @if (ehDono()) { <th class="right">Pago</th><th class="right">Saldo</th> }<th></th></tr></thead>
          <tbody>
            @for (o of d.ordens; track o.id) {
              <tr>
                <td class="nowrap">{{ quando(o.criada_em) }}</td>
                <td class="right nowrap">{{ o.km_entrada !== null ? km(o.km_entrada) : '—' }}</td>
                <td>{{ o.descricao }}</td>
                <td><span [class]="'badge ' + o.status">{{ rotulo(o.status) }}</span></td>
                <td class="right nowrap">{{ dinheiro(o.valor_total_centavos) }}</td>
                @if (ehDono()) {
                  <td class="right nowrap">{{ dinheiro(o.pago_centavos) }}</td>
                  <td class="right nowrap">{{ dinheiro(saldo(o)) }}</td>
                }
                <td class="right"><a class="btn sm" [routerLink]="['/app/os', o.id]" [attr.aria-label]="'Abrir OS #' + o.id">Abrir</a></td>
              </tr>
            }
          </tbody>
        </table></div></div>
      }
    } @else { <p class="muted">Carregando…</p> }
  `,
})
export class VeiculoHistorico implements OnInit {
  private api = inject(Api);
  private id = Number(inject(ActivatedRoute).snapshot.paramMap.get('id'));
  dados = signal<Historico | null>(null);
  naoEncontrado = signal(false); erro = signal('');
  ehDono = computed(() => this.api.user()?.role === 'dono');
  rotulo = (s: string) => STATUS_LABEL[s] ?? s;
  dinheiro = reais; quando = dataHora;
  km = (n: number) => n.toLocaleString('pt-BR') + ' km';
  saldo = (o: OsHistorico) => Math.max(0, (o.valor_devido_centavos ?? 0) - (o.pago_centavos ?? 0));

  async ngOnInit() {
    if (!Number.isInteger(this.id) || this.id < 1) { this.naoEncontrado.set(true); return; }
    try { this.dados.set(await this.api.get<Historico>(`/api/veiculos/${this.id}/historico`)); }
    catch (e) {
      const err = e as ApiError;
      if (err.status === 404) this.naoEncontrado.set(true); else this.erro.set(err.message);
    }
  }
}
