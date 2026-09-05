import { Component } from '@angular/core';
import { RouterLink, RouterLinkActive, RouterOutlet } from '@angular/router';

interface NavItem {
  label: string;
  icon: string;
  route: string;
  badge?: number;
}

interface NavGroup {
  title: string;
  items: NavItem[];
}

@Component({
  selector: 'app-admin-layout',
  imports: [RouterLink, RouterLinkActive, RouterOutlet],
  templateUrl: './admin-layout.html',
  styleUrl: './admin-layout.css'
})
export class AdminLayout {
  protected readonly navGroups: NavGroup[] = [
    {
      title: 'General',
      items: [
        { label: 'Inicio', icon: 'home', route: '/admin/inicio' },
        { label: 'Reportes', icon: 'chart', route: '/admin/reportes' },
        { label: 'Tiempo real', icon: 'clock', route: '/admin/tiempo-real' }
      ]
    },
    {
      title: 'Operación',
      items: [
        { label: 'Viajes', icon: 'route', route: '/admin/viajes' },
        { label: 'Buses', icon: 'bus', route: '/admin/buses' },
        { label: 'Conductores', icon: 'drivers', route: '/admin/conductores' }
      ]
    },
    {
      title: 'Comercial',
      items: [
        { label: 'Tiquetes', icon: 'ticket', route: '/admin/tiquetes' },
        { label: 'Usuarios', icon: 'users', route: '/admin/usuarios' },
        { label: 'Soporte', icon: 'support', route: '/admin/soporte', badge: 3 }
      ]
    }
  ];

  protected readonly currentUser = {
    name: 'Brayan Rada',
    role: 'Administrador'
  };
}
