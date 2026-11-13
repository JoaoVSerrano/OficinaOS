import { Component, OnInit, inject, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { ActivatedRoute, RouterLink } from '@angular/router';
import { Api, ApiError } from '../../core/api';
import { AUTH_STYLES } from './auth-base';

@Component({
  selector: 'app-recuperar',
  imports: [FormsModule, RouterLink],
  styles: [AUTH_STYLES],
  template: `
    <div class="wrap"><div class="box">
      <a class="logo" routerLink="/">Oficina<span>OS</span></a>
      <div class="card">
        @if (token) {
          <h1>Nova senha</h1>
          @if (erro()) { <div class="alert err" role="alert">{{ erro() }}</div> }
          @if (ok()) { <div class="alert ok">Senha alterada. <a routerLink="/entrar">Entrar</a></div> }
          @else if (tokenValido()) {
            <form (ngSubmit)="redefinir()">
              <div class="field"><label for="ns">Nova senha</label><input id="ns" name="ns" type="password" minlength="6" autocomplete="new-password" [(ngModel)]="novaSenha" required></div>
              <button class="btn primary block" type="submit">Salvar nova senha</button>
            </form>
          }
        } @else {
          <h1>Recuperar senha</h1>
          @if (erro()) { <div class="alert err" role="alert">{{ erro() }}</div> }
          @if (ok()) { <div class="alert ok">Se o e-mail existir, enviamos um link para redefinir a senha.</div> }
          @else {
            <form (ngSubmit)="solicitar()">
              <div class="field"><label for="email">E-mail da conta</label><input id="email" name="email" type="email" [(ngModel)]="email" required></div>
              <button class="btn primary block" type="submit">Enviar link</button>
            </form>
          }
        }
        <div class="links"><a routerLink="/entrar">Voltar para entrar</a></div>
      </div>
    </div></div>
  `,
})
export class Recuperar implements OnInit {
  private api = inject(Api);
  private route = inject(ActivatedRoute);
  token = this.route.snapshot.queryParamMap.get('token') ?? '';
  email = ''; novaSenha = '';
  erro = signal(''); ok = signal(false); tokenValido = signal(false);

  async ngOnInit() {
    if (!this.token) return;
    try { await this.api.get('/api/auth/reset-password/check', { token: this.token }); this.tokenValido.set(true); }
    catch (e) { this.erro.set((e as ApiError).message); }
  }
  async solicitar() {
    this.erro.set('');
    try { await this.api.post('/api/auth/forgot-password', { email: this.email }); this.ok.set(true); }
    catch (e) { this.erro.set((e as ApiError).message); }
  }
  async redefinir() {
    this.erro.set('');
    try { await this.api.post('/api/auth/reset-password', { token: this.token, nova_senha: this.novaSenha }); this.ok.set(true); }
    catch (e) { this.erro.set((e as ApiError).message); }
  }
}
