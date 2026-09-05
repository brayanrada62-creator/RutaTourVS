import { Component } from '@angular/core';
import { CommonModule } from '@angular/common';
import { Sidebar } from '../../shared/sidebar/sidebar';
import { Topbar } from '../../shared/topbar/topbar';

interface StatCard {
  label: string;
  value: string;
  hint: string;
}

interface SalesDay {
  day: string;
  value: number; 
}

interface ActivityItem {
  text: string;
  time: string;
}

@Component({
  selector: 'app-dashboard',
  standalone: true,
  imports: [CommonModule, Sidebar, Topbar],
  templateUrl: './dashboard.html',
  styleUrl: './dashboard.css'
})
export class Dashboard {
  // TODO: obtener el nombre del usuario autenticado (ej. desde un AuthService / token de sesión)
  userName = '';

  // TODO: obtener el nombre de la plataforma/agencia principal desde el backend
  platformName = '';

  // TODO: llamar al endpoint de métricas del backend (agencias activas, ventas de hoy,
  // viajes activos, usuarios totales) y llenar este arreglo con la respuesta.
  stats: StatCard[] = [];

  // TODO: llamar al endpoint de ventas semanales del backend y llenar este arreglo
  // con los datos reales (día y valor/porcentaje de la barra).
  weeklySales: SalesDay[] = [];

  // TODO: llamar al endpoint de actividad reciente del backend y llenar este arreglo
  // con los últimos eventos de la plataforma.
  recentActivity: ActivityItem[] = [];
}