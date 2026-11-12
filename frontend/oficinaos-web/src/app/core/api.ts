import { HttpClient, HttpErrorResponse } from '@angular/common/http';
import { Injectable, inject, signal } from '@angular/core';
import { firstValueFrom } from 'rxjs';

export type Papel = 'admin' | 'dono' | 'mecanico' | 'cliente';

export interface User {
  id: number;
  nome: string;
  email: string;
  role: Papel;
  oficina_id: number | null;
  bio?: string;
  avatar_url?: string | null;
}

export interface Veiculo { id: number; cliente_id: number; placa: string; marca: string; modelo: string; ano: number | null; }
export interface Cliente { id: number; nome: string; telefone: string | null; email: string | null; }
export interface Item { id: number; tipo: 'servico' | 'peca'; descricao: string; quantidade: number; valor_unitario_centavos: number; subtotal_centavos: number; }
export interface Anexo { id: number; os_id: number; nome_original: string; tipo_mime: string; tamanho_bytes: number; url: string; criado_em: string; }
export interface Os {
  id: number; status: string; descricao: string; mecanico_id: number | null; valor_total_centavos: number;
  criada_em: string; atualizada_em: string;
  veiculo: { id: number; placa: string; marca: string; modelo: string } | null;
  cliente: { id: number; nome: string } | null;
  itens?: Item[];
}

export interface PlanoInfo {
  plano: 'free' | 'pro'; nome: string; status: string; inadimplente: boolean;
  periodo_fim: string | null; valor_mensal_centavos: number; preco_pro_centavos: number;
  uso: { os_mes: number; mecanicos: number };
  limites: { max_os_mes: number | null; max_mecanicos: number | null; max_anexos_por_os: number | null };
  pode_gerenciar: boolean;
}

/** Erro de API já traduzido para a interface. */
export class ApiError extends Error {
  constructor(message: string, public status: number, public corpo: any) { super(message); }
  get limitePlano(): boolean { return this.status === 402 && this.corpo?.codigo === 'limite_plano'; }
}

export const STATUS_LABEL: Record<string, string> = {
  aberta: 'Aberta', orcamento_aprovado: 'Orçamento aprovado', em_servico: 'Em serviço',
  pronta: 'Pronta', entregue: 'Entregue', cancelada: 'Cancelada',
};
export const PAPEL_LABEL: Record<string, string> = {
  admin: 'Administrador', dono: 'Dono da oficina', mecanico: 'Mecânico', cliente: 'Cliente',
};

@Injectable({ providedIn: 'root' })
export class Api {
  private http = inject(HttpClient);
  /** undefined = ainda não carregou; null = sem sessão. */
  readonly user = signal<User | null | undefined>(undefined);
  /** Plano da oficina (dono e mecânico); null = ainda não carregou ou sem acesso. */
  readonly plano = signal<PlanoInfo | null>(null);

  private async call<T>(req: Promise<T>): Promise<T> {
    try {
      return await req;
    } catch (e) {
      const err = e as HttpErrorResponse;
      const msg = err.error?.error ?? (err.status === 0 ? 'Sem conexão com o servidor.' : 'Algo deu errado. Tente novamente.');
      throw new ApiError(msg, err.status, err.error);
    }
  }
  get<T>(url: string, params?: Record<string, string | number>) { return this.call(firstValueFrom(this.http.get<T>(url, { params: params as any }))); }
  post<T>(url: string, body: unknown = {}) { return this.call(firstValueFrom(this.http.post<T>(url, body))); }
  put<T>(url: string, body: unknown = {}) { return this.call(firstValueFrom(this.http.put<T>(url, body))); }
  delete<T>(url: string) { return this.call(firstValueFrom(this.http.delete<T>(url))); }

  async carregarUsuario(): Promise<User | null> {
    try {
      const r = await this.get<{ user: User | null }>('/api/auth/me');
      this.user.set(r.user);
      return r.user;
    } catch {
      this.user.set(null);
      return null;
    }
  }
  async carregarPlano(): Promise<PlanoInfo | null> {
    const papel = this.user()?.role;
    if (papel !== 'dono' && papel !== 'mecanico') { this.plano.set(null); return null; }
    try { this.plano.set(await this.get<PlanoInfo>('/api/plano')); } catch { this.plano.set(null); }
    return this.plano();
  }
  async garantirUsuario(): Promise<User | null> {
    const atual = this.user();
    return atual === undefined ? this.carregarUsuario() : atual;
  }
  async sair() {
    try { await this.post('/api/auth/logout'); } finally { this.user.set(null); }
  }
}

export function reais(centavos: number | null | undefined): string {
  return ((centavos ?? 0) / 100).toLocaleString('pt-BR', { style: 'currency', currency: 'BRL' });
}
/** "45,90" ou "45.90" -> 4590. NaN se inválido. */
export function paraCentavos(texto: string): number {
  const n = Number(String(texto).trim().replace(/\./g, '').replace(',', '.'));
  return Number.isFinite(n) && n >= 0 ? Math.round(n * 100) : NaN;
}
export function dataHora(iso: string | null | undefined): string {
  if (!iso) return '';
  return new Date(iso).toLocaleString('pt-BR', { dateStyle: 'short', timeStyle: 'short' });
}
