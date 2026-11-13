import { Component, OnDestroy, OnInit, inject, signal } from '@angular/core';
import { ActivatedRoute } from '@angular/router';
import { Api, ApiError, dataHora, reais } from '../../core/api';

type Retorno = 'ok' | 'cancelada' | '';

@Component({
  selector: 'app-plano',
  styles: [`
    .barra { height: 10px; border-radius: 999px; background: var(--line); overflow: hidden; margin: 6px 0 2px; }
    .barra > span { display: block; height: 100%; background: var(--brand); }
    .barra.cheia > span { background: var(--bad); }
    .uso { margin-bottom: 14px; }
    .acoes { display: flex; gap: 10px; flex-wrap: wrap; margin-top: 12px; }
  `],
  template: `
    <h1>Plano e assinatura</h1>
    @if (erro()) { <div class="alert err" role="alert">{{ erro() }}</div> }
    @if (processando()) {
      <div class="alert info" role="status">Processando seu pagamento… confirmando com a Stripe. Isso leva alguns segundos.</div>
    }
    @if (retorno() === 'ok' && !processando() && p()?.plano === 'pro') {
      <div class="alert ok" role="status">Assinatura confirmada. Sua oficina agora é Pro, sem limites.</div>
    }
    @if (demorou()) {
      <div class="alert warn" role="status">A confirmação ainda não chegou. Pode levar mais um pouco: atualize a página em instantes.
        Se o valor foi cobrado e o plano não mudar, fale com o suporte.</div>
    }
    @if (retorno() === 'cancelada') { <div class="alert info" role="status">Pagamento cancelado. Nada foi cobrado.</div> }

    @if (p(); as d) {
      @if (d.inadimplente) {
        <div class="alert warn" role="alert">O último pagamento da assinatura falhou.
          @if (d.pode_gerenciar) { Atualize a forma de pagamento em “Gerenciar assinatura”. } @else { Avise o dono da oficina. }</div>
      }
      <div class="card">
        <h2>Plano {{ d.nome }} <span class="badge">{{ d.plano === 'pro' ? 'Pro' : 'Free' }}</span></h2>
        @if (d.plano === 'pro') {
          <p>{{ reais(d.valor_mensal_centavos) }} por mês@if (d.periodo_fim) {, próxima renovação em {{ data(d.periodo_fim) }}}.
            Sem limite de ordens de serviço, mecânicos ou anexos.</p>
        } @else {
          <p>Grátis. Para crescer sem limites, assine o Pro por {{ reais(d.preco_pro_centavos) }} por mês.</p>
        }

        <h3>Uso neste mês</h3>
        <div class="uso">
          <div>Ordens de serviço: <strong>{{ d.uso.os_mes }}{{ d.limites.max_os_mes !== null ? ' de ' + d.limites.max_os_mes : '' }}</strong></div>
          @if (d.limites.max_os_mes !== null) {
            <div class="barra" [class.cheia]="d.uso.os_mes >= d.limites.max_os_mes" role="progressbar"
              [attr.aria-valuenow]="d.uso.os_mes" aria-valuemin="0" [attr.aria-valuemax]="d.limites.max_os_mes"
              aria-label="Ordens de serviço usadas"><span [style.width.%]="pct(d.uso.os_mes, d.limites.max_os_mes)"></span></div>
          }
        </div>
        <div class="uso">
          <div>Mecânicos: <strong>{{ d.uso.mecanicos }}{{ d.limites.max_mecanicos !== null ? ' de ' + d.limites.max_mecanicos : '' }}</strong></div>
          @if (d.limites.max_mecanicos !== null) {
            <div class="barra" [class.cheia]="d.uso.mecanicos >= d.limites.max_mecanicos" role="progressbar"
              [attr.aria-valuenow]="d.uso.mecanicos" aria-valuemin="0" [attr.aria-valuemax]="d.limites.max_mecanicos"
              aria-label="Mecânicos usados"><span [style.width.%]="pct(d.uso.mecanicos, d.limites.max_mecanicos)"></span></div>
          }
        </div>
        @if (d.limites.max_anexos_por_os !== null) { <p class="muted">Até {{ d.limites.max_anexos_por_os }} anexos por ordem de serviço.</p> }

        @if (d.pode_gerenciar) {
          <div class="acoes">
            @if (d.plano === 'free') {
              <button class="btn primary" type="button" [disabled]="ocupado()" (click)="assinar()">Assinar Pro</button>
            }
            @if (d.plano === 'pro' || d.status !== 'free') {
              <button class="btn" type="button" [disabled]="ocupado()" (click)="gerenciar()">Gerenciar assinatura</button>
            }
          </div>
        } @else {
          <p class="muted">Só o dono da oficina pode assinar ou gerenciar o plano.</p>
        }
      </div>
    } @else if (!erro()) { <p class="muted">Carregando…</p> }
  `,
})
export class Plano implements OnInit, OnDestroy {
  private api = inject(Api);
  private rota = inject(ActivatedRoute);
  p = this.api.plano;
  erro = signal('');
  ocupado = signal(false);
  processando = signal(false);
  demorou = signal(false);
  retorno = signal<Retorno>('');
  reais = reais;
  data = (iso: string) => dataHora(iso);
  pct = (uso: number, limite: number) => Math.min(100, Math.round((uso / limite) * 100));
  private timer: ReturnType<typeof setTimeout> | undefined;

  async ngOnInit() {
    const r = this.rota.snapshot.queryParamMap.get('assinatura');
    this.retorno.set(r === 'ok' || r === 'cancelada' ? r : '');
    await this.api.carregarPlano();
    // Voltou do checkout: o plano só muda quando o WEBHOOK chega, então espera e consulta de novo.
    if (this.retorno() === 'ok' && this.p()?.plano !== 'pro') this.aguardarWebhook(0);
  }
  ngOnDestroy() { clearTimeout(this.timer); }

  private aguardarWebhook(tentativa: number) {
    this.processando.set(true);
    this.timer = setTimeout(async () => {
      await this.api.carregarPlano();
      if (this.p()?.plano === 'pro') { this.processando.set(false); return; }
      if (tentativa >= 14) { this.processando.set(false); this.demorou.set(true); return; }
      this.aguardarWebhook(tentativa + 1);
    }, 2000);
  }

  async assinar() { await this.ir('/api/payment/checkout', 'checkout_url'); }
  async gerenciar() { await this.ir('/api/payment/portal', 'portal_url'); }
  private async ir(url: string, campo: string) {
    this.erro.set(''); this.ocupado.set(true);
    try {
      const r = await this.api.post<Record<string, string>>(url);
      window.location.assign(r[campo]);
    } catch (e) { this.erro.set((e as ApiError).message); this.ocupado.set(false); }
  }
}
