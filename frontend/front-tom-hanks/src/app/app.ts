import { CommonModule, isPlatformBrowser } from '@angular/common';
import { Component, OnInit, PLATFORM_ID, computed, inject, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';

type AuthMode = 'login' | 'register' | 'forgot' | 'reset';

interface User {
  id: number;
  nome: string;
  email: string;
  role: 'usuario' | 'admin' | string;
  bio?: string;
  avatar_key?: string;
  avatar_url?: string;
  google_id?: string;
  criado_em?: string;
}

interface MovieComment {
  id: number;
  usuario_id: number;
  tmdb_movie_id: number;
  texto: string;
  criado_em: string;
}

interface AdminUser {
  id: number;
  nome: string;
  email: string;
  role: 'usuario' | 'admin' | string;
  criado_em?: string;
}

interface MovieCard {
  tmdb_movie_id: number;
  title: string;
  overview: string;
  poster_url: string | null;
  poster_path?: string | null;
  release_date?: string | null;
  is_favorite: boolean;
  favorite?: boolean;
  comment_count: number;
  comments: MovieComment[];
  commentDraft: string;
}

interface CatalogResponse {
  user_id: number;
  movies: MovieCard[];
  favorites: MovieCard[];
  stats: {
    favorite_count: number;
    comment_count: number;
  };
  warning?: string;
}

interface AuthResponse {
  user: User;
}

interface SessionResponse {
  user: User | null;
}

interface PlanDetails {
  name: string;
  currency: string;
  formatted_price: string;
  interval: string;
  price_id?: string;
}

interface PremiumStatus {
  has_premium: boolean;
  entitlement?: {
    has_premium: boolean;
    status: string;
    plan?: string | null;
    period_end?: string | null;
    is_admin?: boolean;
    stripe_status?: string;
  };
}

interface PremiumMovie {
  tmdb_movie_id: number;
  title: string;
  overview: string;
  poster_url: string | null;
  poster_path?: string | null;
  release_date?: string | null;
  job?: string;
  department?: string;
}

interface PremiumInsights {
  total_movies: number;
  movies_by_decade: Record<string, number>;
  average_rating: number | null;
  top_genres: Array<{ genre: string; count: number }>;
  career_start_year?: number;
  career_years?: number;
  career_headline?: string;
  roles_by_decade?: Record<string, Record<string, number>>;
  weighted_average_rating?: number;
  min_votes_filter?: number;
  top_movie_by_decade?: Record<string, any>;
  financial_highlights?: Array<{
    title: string;
    year: string;
    revenue: string;
    budget: string;
    poster_url?: string | null;
  }>;
  attribution?: string;
}

interface InfraHealthService {
  name: string;
  status: string;
  http_status: number | null;
  latency_ms?: number;
  version?: string;
  uptime_seconds?: number | null;
  timestamp?: string;
  dependencies?: Record<string, any>;
  details?: Record<string, any>;
  error?: string | null;
}

interface InfraHealthResponse {
  overall: string;
  timestamp?: string;
  services: InfraHealthService[];
}

interface RedisInfoResponse {
  status: string;
  version?: string;
  uptime_seconds?: number;
  connected_clients?: number;
  used_memory_mb?: number;
  used_memory_human?: string;
  maxmemory_human?: string;
  ops_per_sec?: number;
  streams?: Array<{ stream_key: string; length: number | null; error?: string }>;
  error?: string;
}

interface SwaggerLink {
  name: string;
  swagger_ui: string;
  openapi_json: string;
}

interface AuditLog {
  event_id: string;
  usuario_id: number | null;
  usuario_nome?: string | null;
  usuario_email?: string | null;
  acao: string;
  detalhe: string | null;
  detalhe_json?: Record<string, any> | null;
  ip: string | null;
  ts_ms: number;
}

@Component({
  selector: 'app-root',
  standalone: true,
  imports: [CommonModule, FormsModule],
  templateUrl: './app.html',
  styleUrl: './app.css',
})
export class App implements OnInit {
  private readonly platformId = inject(PLATFORM_ID);

  protected readonly authMode = signal<AuthMode>('login');
  protected readonly user = signal<User | null>(null);
  protected readonly movies = signal<MovieCard[]>([]);
  protected readonly adminUsers = signal<AdminUser[]>([]);
  protected readonly favorites = computed(() => this.movies().filter((movie) => movie.is_favorite));
  protected readonly favoriteCount = computed(() => this.favorites().length);
  protected readonly commentCount = computed(() =>
    this.movies().reduce((total, movie) => total + movie.comments.length, 0),
  );

  // Premium Signals
  protected readonly isPremium = signal(false);
  protected readonly premiumStatus = signal<PremiumStatus | null>(null);
  protected readonly premiumMovies = signal<PremiumMovie[]>([]);
  protected readonly premiumInsights = signal<PremiumInsights | null>(null);
  protected readonly planDetails = signal<PlanDetails>({
    name: 'Plano Premium',
    currency: 'brl',
    formatted_price: 'R$ 9,90',
    interval: 'mês',
  });
  protected readonly activeTab = signal<'catalog' | 'premium' | 'admin'>('catalog');

  // Admin Infra Signals
  protected readonly infraHealth = signal<InfraHealthResponse | null>(null);
  protected readonly redisInfo = signal<RedisInfoResponse | null>(null);
  protected readonly swaggerLinks = signal<SwaggerLink[]>([]);
  protected readonly adminLogs = signal<AuditLog[]>([]);
  protected readonly infraRefreshing = signal(false);
  protected readonly lastUpdated = signal<string>('');
  protected readonly autoRefreshInterval = signal<number>(0); // 0 = off, 15, 30, 60
  private autoRefreshTimer: any = null;

  // Logs filters & pagination
  protected readonly logFilterAction = signal<string>('');
  protected readonly logFilterUser = signal<string>('');
  protected readonly logFilterStartDate = signal<string>('');
  protected readonly logFilterEndDate = signal<string>('');
  protected readonly logStreamTotal = signal<number | null>(null);
  protected readonly logCurrentLimit = signal<number>(50);

  // Favorite request lock (idempotência e prevenção de duplo clique)
  protected readonly pendingFavorites = signal<Set<number>>(new Set<number>());

  // Toast / Notice Auto-Dismiss & Pause
  private noticeTimer: any = null;
  private noticeTimeRemaining: number = 5000;
  private noticeStartTime: number = 0;
  private noticePaused: boolean = false;

  protected readonly posterFallback =
    "data:image/svg+xml;charset=UTF-8," +
    encodeURIComponent(
      `<svg xmlns="http://www.w3.org/2000/svg" width="500" height="750" viewBox="0 0 500 750"><defs><linearGradient id="g" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="#0f172a"/><stop offset="1" stop-color="#7c2d12"/></linearGradient></defs><rect width="500" height="750" fill="url(#g)"/><text x="50%" y="46%" text-anchor="middle" fill="#f8fafc" font-family="Arial, sans-serif" font-size="42" font-weight="700">Tom Hanks</text><text x="50%" y="54%" text-anchor="middle" fill="#e2e8f0" font-family="Arial, sans-serif" font-size="20">Poster indisponivel</text></svg>`,
    );
  protected readonly loading = signal(false);
  protected readonly ready = signal(true);
  protected readonly notice = signal('');
  protected readonly error = signal('');

  protected readonly registerForm = {
    nome: '',
    email: '',
    senha: '',
  };

  protected readonly loginForm = {
    email: '',
    senha: '',
  };

  protected readonly forgotForm = {
    email: '',
  };

  protected readonly resetForm = {
    senha: '',
  };

  protected readonly resetToken = signal<string | null>(null);

  protected readonly profileForm = {
    nome: '',
    bio: '',
  };
  protected readonly editingProfile = signal(false);
  protected selectedAvatarFile: File | null = null;

  protected openEditProfile(): void {
    const u = this.user();
    if (u) {
      this.profileForm.nome = u.nome || '';
      this.profileForm.bio = u.bio || '';
      this.editingProfile.set(true);
    }
  }

  protected closeEditProfile(): void {
    this.editingProfile.set(false);
    this.selectedAvatarFile = null;
  }

  protected onAvatarSelected(event: Event): void {
    const input = event.target as HTMLInputElement;
    if (input.files && input.files.length > 0) {
      this.selectedAvatarFile = input.files[0];
    }
  }

  protected async saveProfile(event?: Event): Promise<void> {
    event?.preventDefault();
    const u = this.user();
    if (!u) return;

    this.loading.set(true);
    this.error.set('');
    this.notice.set('');

    try {
      const res = await fetch(`/api/profile/${u.id}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        credentials: 'include',
        body: JSON.stringify(this.profileForm),
      });
      const data = await res.json();
      if (!res.ok) {
        throw new Error(data.error || 'Falha ao atualizar perfil');
      }

      let updatedUser = data.user || u;

      if (this.selectedAvatarFile) {
        const formData = new FormData();
        formData.append('avatar', this.selectedAvatarFile);

        const avatarRes = await fetch(`/api/profile/${u.id}/avatar`, {
          method: 'POST',
          credentials: 'include',
          body: formData,
        });
        const avatarData = await avatarRes.json();
        if (!avatarRes.ok) {
          throw new Error(avatarData.error || 'Falha ao fazer upload da foto de perfil');
        }
        if (avatarData.user) {
          updatedUser = avatarData.user;
        }
      }

      this.user.set(updatedUser);
      this.notice.set('Perfil e foto atualizados com sucesso!');
      this.closeEditProfile();
    } catch (err: any) {
      this.error.set(err.message || 'Erro ao salvar perfil');
    } finally {
      this.loading.set(false);
    }
  }

  ngOnInit(): void {
    if (isPlatformBrowser(this.platformId)) {
      void this.bootstrap();
    }
  }

  protected trackMovie = (_: number, movie: MovieCard) => movie.tmdb_movie_id;

  protected switchMode(mode: AuthMode): void {
    this.authMode.set(mode);
    this.error.set('');
    this.notice.set('');
  }

  protected async loginWithGoogle(): Promise<void> {
    this.loading.set(true);
    this.error.set('');
    try {
      const data = await this.requestJson<{ url: string }>('/api/auth/google/url');
      if (data?.url) {
        window.location.href = data.url;
      } else {
        throw new Error('URL de autenticação Google não disponível.');
      }
    } catch (err) {
      this.error.set(this.messageFromError(err));
      this.loading.set(false);
    }
  }

  protected async submitAuth(event?: Event): Promise<void> {
    event?.preventDefault();
    const mode = this.authMode();
    const form = event?.currentTarget;
    const formData = form instanceof HTMLFormElement ? new FormData(form) : null;

    const formValue = (name: string, fallback: string): string => {
      const value = formData?.get(name);
      return typeof value === 'string' && value.trim().length > 0 ? value : fallback;
    };

    if (mode === 'login') {
      this.loginForm.email = formValue('email', this.loginForm.email).trim();
      this.loginForm.senha = formValue('senha', this.loginForm.senha);
      if (!this.loginForm.email || !this.loginForm.senha) {
        this.error.set('Informe e-mail e senha para entrar.');
        return;
      }
    }

    if (mode === 'register') {
      this.registerForm.nome = formValue('nome', this.registerForm.nome).trim();
      this.registerForm.email = formValue('email', this.registerForm.email).trim();
      this.registerForm.senha = formValue('senha', this.registerForm.senha);
      if (!this.registerForm.nome || !this.registerForm.email || !this.registerForm.senha) {
        this.error.set('Preencha nome, e-mail e senha para criar a conta.');
        return;
      }
    }

    this.loading.set(true);
    this.error.set('');
    this.notice.set('');

    try {
      let response: AuthResponse;
      if (mode === 'register') {
        const payload = {
          nome: this.registerForm.nome.trim(),
          email: this.registerForm.email.trim(),
          senha: this.registerForm.senha,
        };
        response = await this.requestJson<AuthResponse>('/api/auth/register', {
          method: 'POST',
          body: JSON.stringify(payload),
        });
      } else if (mode === 'login') {
        const payload = {
          email: this.loginForm.email.trim(),
          senha: this.loginForm.senha,
        };
        response = await this.requestJson<AuthResponse>('/api/auth/login', {
          method: 'POST',
          body: JSON.stringify(payload),
        });
      } else {
        return;
      }

      const session = await this.requestJson<SessionResponse>('/api/auth/me');
      if (!session.user) {
        this.user.set(null);
        this.movies.set([]);
        throw new Error('Login concluído, mas a sessão não foi preservada. Tente novamente.');
      }
      this.user.set(session.user);
      this.notice.set(
        mode === 'register'
          ? `Conta criada para ${response.user.nome}.`
          : `Bem-vindo, ${response.user.nome}.`,
      );
      this.resetAuthForms();
      await this.loadCatalog();
      await this.checkPremiumStatus();
      await this.loadAdminUsersIfNeeded();
    } catch (error) {
      this.error.set(this.messageFromError(error));
    } finally {
      this.loading.set(false);
    }
  }

  protected async logout(): Promise<void> {
    this.loading.set(true);
    try {
      await this.requestJson('/api/auth/logout', { method: 'POST' });
    } catch {
      // Ignore logout errors and clear local state
    } finally {
      this.user.set(null);
      this.movies.set([]);
      this.adminUsers.set([]);
      this.isPremium.set(false);
      this.premiumStatus.set(null);
      this.premiumMovies.set([]);
      this.premiumInsights.set(null);
      this.activeTab.set('catalog');
      this.notice.set('Sessão encerrada.');
      this.error.set('');
      this.loading.set(false);
    }
  }

  protected async refreshCatalog(): Promise<void> {
    await this.loadCatalog();
  }

  // Stripe & Premium Actions
  protected async startCheckout(): Promise<void> {
    this.loading.set(true);
    this.error.set('');
    try {
      const resp = await this.requestJson<{ checkout_url: string }>('/api/payment/checkout', {
        method: 'POST',
      });
      if (resp?.checkout_url) {
        window.location.href = resp.checkout_url;
      } else {
        throw new Error('Link de checkout da Stripe não foi gerado.');
      }
    } catch (err: any) {
      this.error.set(this.messageFromError(err));
    } finally {
      this.loading.set(false);
    }
  }

  protected async openCustomerPortal(): Promise<void> {
    this.loading.set(true);
    this.error.set('');
    try {
      const resp = await this.requestJson<{ portal_url: string }>('/api/payment/portal', {
        method: 'POST',
      });
      if (resp?.portal_url) {
        window.location.href = resp.portal_url;
      } else {
        throw new Error('Link do portal do cliente Stripe não foi gerado.');
      }
    } catch (err: any) {
      this.error.set(this.messageFromError(err));
    } finally {
      this.loading.set(false);
    }
  }

  protected async checkPremiumStatus(): Promise<void> {
    try {
      const status = await this.requestJson<PremiumStatus>('/api/premium/status');
      this.isPremium.set(Boolean(status?.has_premium));
      this.premiumStatus.set(status);
      if (status?.has_premium) {
        void this.loadPremiumData();
      }
    } catch {
      this.isPremium.set(false);
      this.premiumStatus.set(null);
    }
  }

  protected async loadPremiumData(): Promise<void> {
    try {
      const [watchlistResp, insightsResp] = await Promise.all([
        this.requestJson<{ movies: PremiumMovie[] }>('/api/premium/watchlist'),
        this.requestJson<PremiumInsights>('/api/premium/insights'),
      ]);
      this.premiumMovies.set(watchlistResp.movies ?? []);
      this.premiumInsights.set(insightsResp ?? null);
    } catch {
      // Ignora erro se não for premium
    }
  }

  // Admin Infra Actions
  protected async openAdminPanel(): Promise<void> {
    this.activeTab.set('admin');
    await this.loadInfraDashboard();
  }

  protected async loadInfraDashboard(): Promise<void> {
    if (this.user()?.role !== 'admin') return;

    this.infraRefreshing.set(true);
    try {
      const results = await Promise.allSettled([
        this.requestJson<InfraHealthResponse>('/api/admin/infra/health'),
        this.requestJson<RedisInfoResponse>('/api/admin/infra/redis'),
        this.requestJson<{ services: SwaggerLink[] }>('/api/admin/infra/swagger-links'),
        this.requestJson<{ logs: AuditLog[] }>('/api/admin/logs?n=50'),
      ]);

      const [health, redis, swaggers, logs] = results;
      if (health.status === 'fulfilled') this.infraHealth.set(health.value);
      if (redis.status === 'fulfilled') this.redisInfo.set(redis.value);
      if (swaggers.status === 'fulfilled') this.swaggerLinks.set(swaggers.value.services ?? []);
      if (logs.status === 'fulfilled') this.adminLogs.set(logs.value.logs ?? []);

      const failed = results.find((result) => result.status === 'rejected');
      if (failed?.status === 'rejected') {
        this.error.set(this.messageFromError(failed.reason));
      }
    } finally {
      this.infraRefreshing.set(false);
    }
  }

  protected async toggleFavorite(movie: MovieCard): Promise<void> {
    this.loading.set(true);
    this.error.set('');
    try {
      if (movie.is_favorite) {
        await this.requestJson(`/api/favorites/${movie.tmdb_movie_id}`, { method: 'DELETE' });
        this.notice.set(`Removido de favoritos: ${movie.title}.`);
      } else {
        await this.requestJson('/api/favorites', {
          method: 'POST',
          body: JSON.stringify({ tmdb_movie_id: movie.tmdb_movie_id }),
        });
        this.notice.set(`Favorito salvo: ${movie.title}.`);
      }
      await this.loadCatalog();
    } catch (error) {
      this.error.set(this.messageFromError(error));
    } finally {
      this.loading.set(false);
    }
  }

  protected async saveComment(movie: MovieCard): Promise<void> {
    const texto = movie.commentDraft.trim();
    if (!texto) {
      this.error.set('Escreva um comentário antes de salvar.');
      return;
    }

    this.loading.set(true);
    this.error.set('');
    try {
      await this.requestJson('/api/comments', {
        method: 'POST',
        body: JSON.stringify({
          tmdb_movie_id: movie.tmdb_movie_id,
          texto,
        }),
      });
      movie.commentDraft = '';
      this.notice.set(`Comentário salvo em ${movie.title}.`);
      await this.loadCatalog();
    } catch (error) {
      this.error.set(this.messageFromError(error));
    } finally {
      this.loading.set(false);
    }
  }

  protected async deleteComment(commentId: number): Promise<void> {
    this.loading.set(true);
    this.error.set('');
    try {
      await this.requestJson(`/api/comments/${commentId}`, { method: 'DELETE' });
      this.notice.set('Comentário removido.');
      await this.loadCatalog();
    } catch (error) {
      this.error.set(this.messageFromError(error));
    } finally {
      this.loading.set(false);
    }
  }

  private async bootstrap(): Promise<void> {
    try {
      const urlParams = new URLSearchParams(window.location.search);
      const token = urlParams.get('token');
      if (token) {
        this.user.set(null);
        this.movies.set([]);
        this.resetToken.set(token);
        this.authMode.set('reset');
        this.notice.set('Informe sua nova senha para concluir a recuperação.');
        return;
      }

      if (urlParams.get('payment') === 'success') {
        this.notice.set('🎉 Parabéns! Sua assinatura premium está ativa. Aproveite o catálogo exclusivo.');
      } else if (urlParams.get('payment') === 'cancel') {
        this.notice.set('Pagamento cancelado. Nenhuma cobrança foi realizada.');
      }

      await this.loadSession();
      if (this.user()) {
        await Promise.all([
          this.loadCatalog(),
          this.checkPremiumStatus(),
          this.loadAdminUsersIfNeeded(),
        ]);
        if (this.user()?.role === 'admin') {
          void this.loadInfraDashboard();
        }
      }
    } catch (error) {
      this.error.set(this.messageFromError(error));
    } finally {
      this.ready.set(true);
    }
  }

  private clearUrlToken(): void {
    if (isPlatformBrowser(this.platformId)) {
      const url = new URL(window.location.href);
      url.searchParams.delete('token');
      url.searchParams.delete('payment');
      url.searchParams.delete('google_login');
      window.history.replaceState({}, '', url.pathname + url.search);
    }
  }

  protected async submitForgotPassword(event?: Event): Promise<void> {
    event?.preventDefault();
    const email = this.forgotForm.email.trim();
    if (!email || !email.includes('@')) {
      this.error.set('Informe um e-mail válido.');
      return;
    }

    this.loading.set(true);
    this.error.set('');
    this.notice.set('');

    try {
      const response = await this.requestJson<{ ok: boolean; message: string; reset_link?: string }>(
        '/api/auth/forgot-password',
        {
          method: 'POST',
          body: JSON.stringify({ email }),
        },
      );
      const resetLinkMessage = response.reset_link ? ` Link para teste: ${response.reset_link}` : '';
      this.notice.set(
        `${response.message || 'Se o e-mail estiver cadastrado, você receberá um link em breve.'}${resetLinkMessage}`,
      );
      this.authMode.set('login');
      this.forgotForm.email = '';
    } catch (error) {
      this.error.set(this.messageFromError(error));
    } finally {
      this.loading.set(false);
    }
  }

  protected async submitResetPassword(event?: Event): Promise<void> {
    event?.preventDefault();
    const token = this.resetToken();
    if (!token) {
      this.error.set('Token de redefinição ausente.');
      return;
    }
    const nova_senha = this.resetForm.senha;
    if (nova_senha.length < 6) {
      this.error.set('A senha precisa ter pelo menos 6 caracteres.');
      return;
    }

    this.loading.set(true);
    this.error.set('');
    this.notice.set('');

    try {
      await this.requestJson('/api/auth/reset-password', {
        method: 'POST',
        body: JSON.stringify({ token, nova_senha }),
      });
      this.notice.set('Senha redefinida com sucesso! Você já pode entrar.');
      this.authMode.set('login');
      this.resetForm.senha = '';
      this.resetToken.set(null);
      this.clearUrlToken();
    } catch (error) {
      this.error.set(this.messageFromError(error));
    } finally {
      this.loading.set(false);
    }
  }

  private async loadSession(): Promise<void> {
    try {
      const response = await this.requestJson<SessionResponse>('/api/auth/me');
      this.user.set(response.user ?? null);
    } catch {
      this.user.set(null);
    }
  }

  protected canDeleteComment(comment: MovieComment): boolean {
    const currentUser = this.user();
    return Boolean(
      currentUser &&
        (currentUser.role === 'admin' || Number(comment.usuario_id) === Number(currentUser.id)),
    );
  }

  protected async changeUserRole(target: AdminUser): Promise<void> {
    const nextRole = target.role === 'admin' ? 'usuario' : 'admin';
    this.loading.set(true);
    this.error.set('');
    try {
      const response = await this.requestJson<{ user: AdminUser }>(
        `/api/admin/users/${target.id}/role`,
        {
          method: 'POST',
          body: JSON.stringify({ role: nextRole }),
        },
      );
      this.adminUsers.update((users) =>
        users.map((user) => (user.id === response.user.id ? { ...user, ...response.user } : user)),
      );
      if (this.user()?.id === target.id) {
        await this.loadSession();
      }
      this.notice.set(`${target.nome} agora é ${nextRole === 'admin' ? 'administrador' : 'usuário'}.`);
    } catch (error) {
      this.error.set(this.messageFromError(error));
    } finally {
      this.loading.set(false);
    }
  }

  private async loadAdminUsersIfNeeded(): Promise<void> {
    if (this.user()?.role !== 'admin') {
      this.adminUsers.set([]);
      return;
    }

    try {
      const response = await this.requestJson<{ users: AdminUser[] }>('/api/admin/users');
      this.adminUsers.set(response.users ?? []);
    } catch (error) {
      this.adminUsers.set([]);
      this.error.set(this.messageFromError(error));
    }
  }

  private async loadCatalog(): Promise<void> {
    if (!this.user()) {
      this.movies.set([]);
      return;
    }

    const response = await this.requestJson<CatalogResponse>('/api/catalog');
    this.movies.set(
      response.movies.map((movie) => ({
        ...movie,
        commentDraft: '',
        comments: [...movie.comments],
      })),
    );

    if (response.warning) {
      this.notice.set(response.warning);
    }
  }

  private resetAuthForms(): void {
    this.registerForm.nome = '';
    this.registerForm.email = '';
    this.registerForm.senha = '';
    this.loginForm.email = '';
    this.loginForm.senha = '';
    this.forgotForm.email = '';
    this.resetForm.senha = '';
  }

  private async requestJson<T>(url: string, init: RequestInit = {}): Promise<T> {
    const response = await fetch(url, {
      ...init,
      credentials: 'include',
      headers: {
        'Content-Type': 'application/json',
        ...(init.headers ?? {}),
      },
    });

    const contentType = response.headers.get('content-type') ?? '';
    const body = contentType.includes('application/json') ? await response.json() : null;

    if (!response.ok) {
      const message = body?.error ?? `A requisição falhou com status ${response.status}.`;
      throw new Error(message);
    }

    return body as T;
  }

  private messageFromError(error: unknown): string {
    if (error instanceof Error) {
      return error.message;
    }
    return 'Não foi possível concluir a operação.';
  }
}
