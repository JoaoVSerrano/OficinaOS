import { Component, OnInit, inject, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { Router, RouterLink } from '@angular/router';
import { Api, ApiError } from '../../core/api';
import { AUTH_STYLES } from './auth-base';

@Component({
  selector: 'app-entrar',
  imports: [FormsModule, RouterLink],
  styles: [AUTH_STYLES],
  template: `
    <div class="wrap"><div class="box">
      <a class="logo" routerLink="/">Oficina<span>OS</span></a>
      <form class="card" (ngSubmit)="entrar()">
        <h1>Entrar</h1>
        @if (erro()) { <div class="alert err" role="alert">{{ erro() }}</div> }
        <div class="field"><label for="email">E-mail</label><input id="email" name="email" type="email" autocomplete="username" [(ngModel)]="email" required></div>
        <div class="field"><label for="senha">Senha</label><input id="senha" name="senha" type="password" autocomplete="current-password" [(ngModel)]="senha" required></div>
        <button class="btn primary block" type="submit" [disabled]="enviando()">{{ enviando() ? 'Entrando…' : 'Entrar' }}</button>
        @if (googleUrl()) { <a class="btn block" style="margin-top:8px" [href]="googleUrl()">Entrar com Google</a> }
        <div class="links"><a routerLink="/recuperar-senha">Esqueci minha senha</a><a routerLink="/cadastro">Criar conta grátis</a></div>
      </form>
    </div></div>
  `,
})
export class Entrar implements OnInit {
  private api = inject(Api);
  private router = inject(Router);
  email = ''; senha = '';
  erro = signal(''); enviando = signal(false); googleUrl = signal('');

  async ngOnInit() {
    try { this.googleUrl.set((await this.api.get<{ url: string }>('/api/auth/google/url')).url); } catch { /* Google não configurado */ }
  }
  async entrar() {
    this.erro.set(''); this.enviando.set(true);
    try {
      await this.api.post('/api/auth/login', { email: this.email, senha: this.senha });
      await this.api.carregarUsuario();
      this.router.navigateByUrl('/app');
    } catch (e) { this.erro.set((e as ApiError).message); }
    finally { this.enviando.set(false); }
  }
}
