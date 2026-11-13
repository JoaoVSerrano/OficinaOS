import { Component } from '@angular/core';
import { RouterLink } from '@angular/router';

@Component({
  selector: 'app-nao-encontrada',
  imports: [RouterLink],
  template: `<div class="container" style="padding:80px 16px;text-align:center">
    <h1>Página não encontrada</h1><p class="muted">O endereço não existe ou foi movido.</p>
    <a class="btn primary" routerLink="/">Voltar ao início</a></div>`,
})
export class NaoEncontrada {}
