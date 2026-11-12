import { Routes } from '@angular/router';
import { autenticado, inicio, papel, soLogin } from './core/guards';

export const routes: Routes = [
  { path: '', loadComponent: () => import('./pages/landing').then((m) => m.Landing), title: 'OficinaOS — pare de perder serviço no caderno' },
  { path: 'entrar', loadComponent: () => import('./pages/entrar').then((m) => m.Entrar), title: 'Entrar — OficinaOS' },
  { path: 'cadastro', loadComponent: () => import('./pages/cadastro').then((m) => m.Cadastro), title: 'Criar conta — OficinaOS' },
  { path: 'recuperar-senha', loadComponent: () => import('./pages/recuperar').then((m) => m.Recuperar), title: 'Recuperar senha — OficinaOS' },
  { path: 'criar-oficina', canActivate: [soLogin], loadComponent: () => import('./pages/criar-oficina').then((m) => m.CriarOficina), title: 'Crie sua oficina — OficinaOS' },
  {
    path: 'app',
    canActivate: [autenticado],
    loadComponent: () => import('./shared/shell').then((m) => m.Shell),
    children: [
      { path: '', pathMatch: 'full', canActivate: [inicio], children: [] },
      { path: 'os', loadComponent: () => import('./pages/os-lista').then((m) => m.OsLista), title: 'Ordens de serviço — OficinaOS' },
      { path: 'os/nova', canActivate: [papel('dono', 'mecanico')], loadComponent: () => import('./pages/os-form').then((m) => m.OsForm), title: 'Abrir ordem de serviço — OficinaOS' },
      { path: 'os/:id', loadComponent: () => import('./pages/os-detalhe').then((m) => m.OsDetalhe), title: 'Ordem de serviço — OficinaOS' },
      { path: 'os/:id/editar', canActivate: [papel('dono', 'mecanico')], loadComponent: () => import('./pages/os-form').then((m) => m.OsForm), title: 'Editar ordem de serviço — OficinaOS' },
      { path: 'clientes', canActivate: [papel('dono', 'mecanico')], loadComponent: () => import('./pages/clientes').then((m) => m.Clientes), title: 'Clientes — OficinaOS' },
      { path: 'veiculos', loadComponent: () => import('./pages/veiculos').then((m) => m.Veiculos), title: 'Veículos — OficinaOS' },
      { path: 'equipe', canActivate: [papel('dono')], loadComponent: () => import('./pages/equipe').then((m) => m.Equipe), title: 'Equipe — OficinaOS' },
      { path: 'perfil', loadComponent: () => import('./pages/perfil').then((m) => m.Perfil), title: 'Meu perfil — OficinaOS' },
      { path: 'admin', canActivate: [papel('admin')], loadComponent: () => import('./pages/admin').then((m) => m.Admin), title: 'Painel da plataforma — OficinaOS' },
      { path: 'auditoria', canActivate: [papel('dono', 'admin')], loadComponent: () => import('./pages/auditoria').then((m) => m.Auditoria), title: 'Auditoria — OficinaOS' },
    ],
  },
  { path: '**', loadComponent: () => import('./pages/nao-encontrada').then((m) => m.NaoEncontrada), title: 'Página não encontrada — OficinaOS' },
];
