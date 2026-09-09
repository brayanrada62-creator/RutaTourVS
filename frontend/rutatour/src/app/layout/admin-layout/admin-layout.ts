import { Component, OnInit } from '@angular/core';
import { RouterLink, RouterLinkActive, RouterOutlet } from '@angular/router';
import { AuthService, CurrentUser } from './auth.service';

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
export class AdminLayout implements OnInit {
  // Estructura de navegación del sidebar (fija, no viene de la base de datos)
  protected readonly navGroups: NavGroup[] = [
    {
      title: 'General',
      items: [
        { label: 'Inicio', icon: 'home', route: '/admin/inicio' },
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
    }
  ];

  // Usuario logueado: llega de la base de datos, arranca en blanco
  protected currentUser: CurrentUser = { name: '', role: '' };

  constructor(private authService: AuthService) {}

  ngOnInit(): void {
    this.authService.getCurrentUser().subscribe({
      next: (user) => (this.currentUser = user),
      error: () => (this.currentUser = { name: '', role: '' })
    });
  }
}