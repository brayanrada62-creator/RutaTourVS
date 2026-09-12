import { Routes } from '@angular/router';
import { AdminLayout } from './layout/admin-layout/admin-layout';
import { Inicio } from './pages/inicio/inicio';
import { Reportes } from './pages/reportes/reportes';
import { TiempoReal } from './pages/tiempo-real/tiempo-real';
import { Paquetes } from './pages/paquetes/paquetes';
import { Buses } from './pages/buses/buses';
import { Conductores } from './pages/conductores/conductores';
import { Tiquetes } from './pages/tiquetes/tiquetes';
import { Usuarios } from './pages/usuarios/usuarios';
import { Hoteles } from './pages/hoteles/hoteles';
import { Destinos } from './pages/destinos/destinos';
import { Login } from './login/login';

export const routes: Routes = [
  { path: '', component: Login },
  {
    path: 'admin',
    component: AdminLayout,
    children: [
      { path: '', redirectTo: 'inicio', pathMatch: 'full' },
      { path: 'inicio', component: Inicio },
      { path: 'reportes', component: Reportes },
      { path: 'tiempo-real', component: TiempoReal },
      { path: 'paquetes', component: Paquetes },
      { path: 'buses', component: Buses },
      { path: 'conductores', component: Conductores },
      { path: 'tiquetes', component: Tiquetes },
      { path: 'usuarios', component: Usuarios },
      { path: 'hoteles', component: Hoteles },
      { path: 'destinos', component: Destinos }
    ]
  },
  { path: '**', redirectTo: 'admin/inicio' }
];