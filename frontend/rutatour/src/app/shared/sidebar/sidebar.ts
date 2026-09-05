import { Component, Input } from '@angular/core';
import { CommonModule } from '@angular/common';
import { RouterLink } from '@angular/router';

interface NavItem {
  label: string;
  icon: string;
  path?: string;
  badge?: number;
}

@Component({
  selector: 'app-sidebar',
  standalone: true,
  imports: [CommonModule, RouterLink],
  templateUrl: './sidebar.html'
})
export class Sidebar {
  /** Label de la página activa, ej: "Inicio" o "Reportes generales" */
  @Input() activeLabel = '';

  userName = 'Marian Cruz';
  userRole = 'Superadministrador';

  navGeneral: NavItem[] = [
    { label: 'Inicio', icon: 'home', path: '/' },
    { label: 'Reportes generales', icon: 'chart', path: '/reportes' },
    { label: 'Viajes en tiempo real', icon: 'map' }
  ];

  navPlataforma: NavItem[] = [
    { label: 'Agencias', icon: 'building', badge: 2 },
    { label: 'Usuarios', icon: 'users' }
  ];

  navSoporte: NavItem[] = [
    { label: 'Novedades y quejas', icon: 'headset', badge: 3 }
  ];
}