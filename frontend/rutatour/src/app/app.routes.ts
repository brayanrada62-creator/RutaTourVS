import { Routes } from '@angular/router';
import { AdminLayout } from './layout/admin-layout/admin-layout';
import { Inicio } from './pages/inicio/inicio';
import { EnConstruccion } from './pages/en-construccion/en-construccion';
import { ViajesComponent } from './pages/viajes/viajes';
import { BusesComponent } from './pages/buses/buses';
import { ConductoresComponent } from './pages/conductores/conductores';
export const routes: Routes = [
  { path: '', redirectTo: 'admin/inicio', pathMatch: 'full' },
  {
    path: 'admin',
    component: AdminLayout,
      children: [
      { path: '', redirectTo: 'inicio', pathMatch: 'full' },
      { path: 'inicio', component: Inicio },
      { path: 'reportes', component: EnConstruccion, data: { title: 'Reportes' } },
      { path: 'tiempo-real', component: EnConstruccion, data: { title: 'Tiempo real' } },
      { path: 'viajes', component: ViajesComponent, data: { title: 'Viajes' } },
      { path: 'buses', component: BusesComponent, data: { title: 'Buses' } },
      { path: 'conductores', component: ConductoresComponent, data: { title: 'Conductores' } },
      { path: 'tiquetes', component: EnConstruccion, data: { title: 'Tiquetes' } },
      { path: 'usuarios', component: EnConstruccion, data: { title: 'Usuarios' } },
      { path: 'soporte', component: EnConstruccion, data: { title: 'Soporte' } }
    ]
  },
  { path: '**', redirectTo: 'admin/inicio' }
];
