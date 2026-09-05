import { Routes } from '@angular/router';
import { Dashboard } from './pages/dashboard/dashboard';
import { Reports } from './pages/reports/reports';

export const routes: Routes = [
  { path: '', component: Dashboard },
  { path: 'reportes', component: Reports }
];