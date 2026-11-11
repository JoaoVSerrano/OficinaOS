import { Component, inject, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { Api, ApiError, PAPEL_LABEL } from '../core/api';

@Component({
  selector: 'app-perfil',
  imports: [FormsModule],
  template: `
    <h1>Meu perfil</h1>
    @if (erro()) { <div class="alert err" role="alert">{{ erro() }}</div> }
    @if (ok()) { <div class="alert ok" role="status">{{ ok() }}</div> }
    <div class="card">
      <div class="actions" style="margin-bottom:12px">
        @if (user()?.avatar_url) { <img [src]="user()?.avatar_url" alt="Sua foto de perfil" width="72" height="72" style="border-radius:50%;object-fit:cover"> }
        <div><strong>{{ user()?.email }}</strong><div class="muted small">{{ papel() }}</div></div>
      </div>
      <form (ngSubmit)="salvar()">
        <div class="field"><label for="nome">Nome</label><input id="nome" name="nome" [(ngModel)]="nome" required></div>
        <div class="field"><label for="bio">Sobre você</label><textarea id="bio" name="bio" [(ngModel)]="bio"></textarea></div>
        <button class="btn primary" type="submit">Salvar perfil</button>
      </form>
    </div>
    <div class="card">
      <h2>Foto de perfil</h2>
      <label for="foto">Escolha uma imagem (até 5 MB)</label>
      <input id="foto" type="file" accept="image/*" (change)="enviarFoto($event)">
    </div>
  `,
})
export class Perfil {
  private api = inject(Api);
  user = this.api.user;
  nome = this.user()?.nome ?? ''; bio = this.user()?.bio ?? '';
  erro = signal(''); ok = signal('');
  papel = () => PAPEL_LABEL[this.user()?.role ?? ''] ?? '';

  async salvar() {
    this.erro.set(''); this.ok.set('');
    try { await this.api.put('/api/profile/' + this.user()!.id, { nome: this.nome, bio: this.bio }); await this.api.carregarUsuario(); this.ok.set('Perfil atualizado.'); }
    catch (e) { this.erro.set((e as ApiError).message); }
  }
  async enviarFoto(ev: Event) {
    const input = ev.target as HTMLInputElement;
    const arquivo = input.files?.[0];
    if (!arquivo) return;
    const form = new FormData(); form.append('avatar', arquivo);
    this.erro.set(''); this.ok.set('');
    try { await this.api.post(`/api/profile/${this.user()!.id}/avatar`, form); await this.api.carregarUsuario(); this.ok.set('Foto atualizada.'); }
    catch (e) { this.erro.set((e as ApiError).message); }
  }
}
