import { Component, inject, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { Router } from '@angular/router';
import { Api, ApiError } from '../core/api';
import { AUTH_STYLES } from './auth-base';

@Component({
  selector: 'app-criar-oficina',
  imports: [FormsModule],
  styles: [AUTH_STYLES],
  template: `
    <div class="wrap"><div class="box">
      <span class="logo">Oficina<span>OS</span></span>
      <form class="card" (ngSubmit)="criar()">
        <h1>Crie sua oficina</h1>
        <p class="muted">Sua conta ainda não tem uma oficina. Informe o nome para começar a abrir ordens de serviço.</p>
        @if (erro()) { <div class="alert err" role="alert">{{ erro() }}</div> }
        <div class="field"><label for="nome">Nome da oficina</label><input id="nome" name="nome" [(ngModel)]="nome" required></div>
        <button class="btn primary block" type="submit">Criar oficina</button>
      </form>
    </div></div>
  `,
})
export class CriarOficina {
  private api = inject(Api);
  private router = inject(Router);
  nome = ''; erro = signal('');
  async criar() {
    this.erro.set('');
    try {
      await this.api.post('/api/oficinas', { nome: this.nome });
      await this.api.carregarUsuario();
      this.router.navigateByUrl('/app');
    } catch (e) { this.erro.set((e as ApiError).message); }
  }
}
