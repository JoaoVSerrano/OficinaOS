import { Component, inject, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { Router, RouterLink } from '@angular/router';
import { Api, ApiError } from '../../core/api';
import { AUTH_STYLES } from './auth-base';

type Tipo = 'dono' | 'mecanico' | 'cliente';

@Component({
  selector: 'app-cadastro',
  imports: [FormsModule, RouterLink],
  styles: [AUTH_STYLES],
  template: `
    <div class="wrap"><div class="box">
      <a class="logo" routerLink="/">Oficina<span>OS</span></a>
      <form class="card" (ngSubmit)="cadastrar()">
        <h1>Criar conta grátis</h1>
        @if (erro()) { <div class="alert err" role="alert">{{ erro() }}</div> }
        <fieldset>
          <legend>Eu sou…</legend>
          <div class="opcoes">
            @for (o of opcoes; track o.valor) {
              <label class="opcao" [class.on]="tipo === o.valor">
                <input type="radio" name="tipo" [value]="o.valor" [(ngModel)]="tipo"> {{ o.texto }}
              </label>
            }
          </div>
        </fieldset>
        <div class="field"><label for="nome">Seu nome</label><input id="nome" name="nome" [(ngModel)]="nome" autocomplete="name" required></div>
        @if (tipo === 'dono') {
          <div class="field"><label for="oficina">Nome da oficina</label><input id="oficina" name="oficina" [(ngModel)]="nomeOficina" required></div>
        } @else {
          <div class="field"><label for="codigo">Código de convite da oficina</label>
            <input id="codigo" name="codigo" [(ngModel)]="codigo" placeholder="OF-XXXXXXXX" required>
            <span class="small muted">O dono da oficina vê o código na tela Equipe.</span></div>
        }
        <div class="field"><label for="email">E-mail</label><input id="email" name="email" type="email" autocomplete="username" [(ngModel)]="email" required></div>
        <div class="field"><label for="senha">Senha (mínimo 6 caracteres)</label><input id="senha" name="senha" type="password" autocomplete="new-password" minlength="6" [(ngModel)]="senha" required></div>
        <button class="btn primary block" type="submit" [disabled]="enviando()">{{ enviando() ? 'Criando…' : 'Criar conta grátis' }}</button>
        <div class="links"><span class="muted">Já tem conta?</span><a routerLink="/entrar">Entrar</a></div>
      </form>
    </div></div>
  `,
})
export class Cadastro {
  private api = inject(Api);
  private router = inject(Router);
  opcoes: { valor: Tipo; texto: string }[] = [
    { valor: 'dono', texto: 'Dono da oficina' }, { valor: 'mecanico', texto: 'Mecânico' }, { valor: 'cliente', texto: 'Cliente' },
  ];
  tipo: Tipo = 'dono'; nome = ''; nomeOficina = ''; codigo = ''; email = ''; senha = '';
  erro = signal(''); enviando = signal(false);

  async cadastrar() {
    this.erro.set(''); this.enviando.set(true);
    try {
      await this.api.post('/api/cadastro', {
        tipo: this.tipo, nome: this.nome, email: this.email, senha: this.senha,
        nome_oficina: this.nomeOficina, codigo_convite: this.codigo,
      });
      await this.api.carregarUsuario();
      this.router.navigateByUrl('/app');
    } catch (e) { this.erro.set((e as ApiError).message); }
    finally { this.enviando.set(false); }
  }
}
