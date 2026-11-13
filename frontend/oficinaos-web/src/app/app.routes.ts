import { Routes } from '@angular/router';
import { autenticado, inicio, papel, soLogin } from './core/guards';

export const routes: Routes = [
  { path: '', loadComponent: () => import('./features/publico/landing').then((m) => m.Landing), title: 'OficinaOS — pare de perder serviço no caderno' },
  { path: 'entrar', loadComponent: () => import('./features/auth/entrar').then((m) => m.Entrar), title: 'Entrar — OficinaOS' },
  { path: 'cadastro', loadComponent: () => import('./features/auth/cadastro').then((m) => m.Cadastro), title: 'Criar conta — OficinaOS' },
  { path: 'recuperar-senha', loadComponent: () => import('./features/auth/recuperar').then((m) => m.Recuperar), title: 'Recuperar senha — OficinaOS' },
  { path: 'orcamento/:token', loadComponent: () => import('./features/os/orcamento-doc').then((m) => m.OrcamentoDoc), title: 'Orçamento — OficinaOS' },
  { path: 'criar-oficina', canActivate: [soLogin], loadComponent: () => import('./features/auth/criar-oficina').then((m) => m.CriarOficina), title: 'Crie sua oficina — OficinaOS' },
  {
    path: 'app',
    canActivate: [autenticado],
    loadComponent: () => import('./shared/shell').then((m) => m.Shell),
    children: [
      { path: '', pathMatch: 'full', canActivate: [inicio], children: [] },
      { path: 'os', loadComponent: () => import('./features/os/os-lista').then((m) => m.OsLista), title: 'Ordens de serviço — OficinaOS' },
      { path: 'os/nova', canActivate: [papel('dono', 'mecanico')], loadComponent: () => import('./features/os/os-form').then((m) => m.OsForm), title: 'Abrir ordem de serviço — OficinaOS' },
      { path: 'os/:id', loadComponent: () => import('./features/os/os-detalhe').then((m) => m.OsDetalhe), title: 'Ordem de serviço — OficinaOS' },
      { path: 'os/:id/orcamento', loadComponent: () => import('./features/os/orcamento-doc').then((m) => m.OrcamentoDoc), title: 'Orçamento — OficinaOS' },
      { path: 'os/:id/editar', canActivate: [papel('dono', 'mecanico')], loadComponent: () => import('./features/os/os-form').then((m) => m.OsForm), title: 'Editar ordem de serviço — OficinaOS' },
      { path: 'clientes', canActivate: [papel('dono', 'mecanico')], loadComponent: () => import('./features/cadastros/clientes').then((m) => m.Clientes), title: 'Clientes — OficinaOS' },
      { path: 'veiculos/:id/historico', loadComponent: () => import('./features/cadastros/veiculo-historico').then((m) => m.VeiculoHistorico), title: 'Histórico do veículo — OficinaOS' },
      { path: 'catalogo', canActivate: [papel('dono', 'mecanico')], loadComponent: () => import('./features/catalogo/catalogo').then((m) => m.Catalogo), title: 'Catálogo — OficinaOS' },
      { path: 'financeiro', canActivate: [papel('dono')], loadComponent: () => import('./features/financeiro/financeiro').then((m) => m.Financeiro), title: 'Financeiro — OficinaOS' },
      { path: 'veiculos', loadComponent: () => import('./features/cadastros/veiculos').then((m) => m.Veiculos), title: 'Veículos — OficinaOS' },
      { path: 'equipe', canActivate: [papel('dono')], loadComponent: () => import('./features/equipe/equipe').then((m) => m.Equipe), title: 'Equipe — OficinaOS' },
      { path: 'perfil', loadComponent: () => import('./features/conta/perfil').then((m) => m.Perfil), title: 'Meu perfil — OficinaOS' },
      { path: 'plano', canActivate: [papel('dono', 'mecanico')], loadComponent: () => import('./features/conta/plano').then((m) => m.Plano), title: 'Plano e assinatura — OficinaOS' },
      { path: 'admin', canActivate: [papel('admin')], loadComponent: () => import('./features/admin/admin').then((m) => m.Admin), title: 'Painel da plataforma — OficinaOS' },
      { path: 'auditoria', canActivate: [papel('dono', 'admin')], loadComponent: () => import('./features/admin/auditoria').then((m) => m.Auditoria), title: 'Auditoria — OficinaOS' },
    ],
  },
  { path: '**', loadComponent: () => import('./shared/nao-encontrada').then((m) => m.NaoEncontrada), title: 'Página não encontrada — OficinaOS' },
];
