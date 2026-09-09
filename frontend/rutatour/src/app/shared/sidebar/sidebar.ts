import { Component, Input } from '@angular/core';
import { CommonModule } from '@angular/common';
import { RouterLink, RouterLinkActive } from '@angular/router';
import { CurrentUser } from '../../layout/admin-layout/auth.service';

interface NavItem {
  label: string;
  icon: string;
  path: string;
  badge?: number;
}

@Component({
  selector: 'app-sidebar',
  standalone: true,
  imports: [CommonModule, RouterLink, RouterLinkActive],
  templateUrl: './sidebar.html'
})
export class Sidebar {
  @Input() currentUser: CurrentUser = { name: '', role: '' };

  navGeneral: NavItem[] = [
    { label: 'Inicio', icon: 'home', path: '/admin/inicio' },
    { label: 'Tiempo real', icon: 'clock', path: '/admin/tiempo-real' }
  ];

  navPlataforma: NavItem[] = [
    { label: 'Viajes', icon: 'route', path: '/admin/viajes' },
    { label: 'Buses', icon: 'bus', path: '/admin/buses' },
    { label: 'Conductores', icon: 'drivers', path: '/admin/conductores' }
  ];

  navSoporte: NavItem[] = [
    { label: 'Usuarios', icon: 'users', path: '/admin/usuarios' }
  ];
}