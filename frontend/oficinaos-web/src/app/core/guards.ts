import { inject } from '@angular/core';
import { CanActivateFn, Router } from '@angular/router';
import { Api, Papel } from './api';

/** Exige login. Dono sem oficina é levado ao onboarding "Crie sua oficina". */
export const autenticado: CanActivateFn = async () => {
  const api = inject(Api);
  const router = inject(Router);
  const u = await api.garantirUsuario();
  if (!u) return router.createUrlTree(['/entrar']);
  if (u.role === 'dono' && !u.oficina_id) return router.createUrlTree(['/criar-oficina']);
  return true;
};

/** Só login (usado no onboarding, onde ainda não há oficina). */
export const soLogin: CanActivateFn = async () => {
  const u = await inject(Api).garantirUsuario();
  return u ? true : inject(Router).createUrlTree(['/entrar']);
};

export const papel = (...permitidos: Papel[]): CanActivateFn => async () => {
  const u = await inject(Api).garantirUsuario();
  return u && permitidos.includes(u.role) ? true : inject(Router).createUrlTree(['/app/os']);
};

/** Página inicial do app depende do papel: admin não tem OS, vai para a auditoria. */
export const inicio: CanActivateFn = async () => {
  const u = await inject(Api).garantirUsuario();
  return inject(Router).createUrlTree([u?.role === 'admin' ? '/app/auditoria' : '/app/os']);
};
