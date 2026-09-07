import { Routes } from '@angular/router';
import { AdminLayout } from './layout/admin-layout/admin-layout';
import { Inicio } from './pages/inicio/inicio';
import { EnConstruccion } from './pages/en-construccion/en-construccion';
import {Login} from './login/login'

export const routes: Routes = [
  { path: '', component: Login},
  {
    path: 'admin',
    component: AdminLayout,
    children: [
      { path: '', redirectTo: 'inicio', pathMatch: 'full' },
      { path: 'inicio', component: Inicio },
      { path: 'reportes', component: EnConstruccion, data: { title: 'Reportes' } },
      { path: 'tiempo-real', component: EnConstruccion, data: { title: 'Tiempo real' } },
      { path: 'viajes', component: EnConstruccion, data: { title: 'Viajes' } },
      { path: 'buses', component: EnConstruccion, data: { title: 'Buses' } },
      { path: 'conductores', component: EnConstruccion, data: { title: 'Conductores' } },
      { path: 'tiquetes', component: EnConstruccion, data: { title: 'Tiquetes' } },
      { path: 'usuarios', component: EnConstruccion, data: { title: 'Usuarios' } },
      { path: 'soporte', component: EnConstruccion, data: { title: 'Soporte' } }
    ]
  },
  { path: '**', redirectTo: 'admin/inicio' }
];
