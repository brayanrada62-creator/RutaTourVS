import { Component } from '@angular/core';

interface StatCard {
  label: string;
  value: string;
  trend: string;
  trendPositive: boolean;
}

interface WeeklySale {
  day: string;
  value: number;
}

interface ActivityItem {
  icon: 'trip' | 'ticket' | 'driver';
  title: string;
  subtitle: string;
}

@Component({
  selector: 'app-inicio',
  imports: [],
  templateUrl: './inicio.html',
  styleUrl: './inicio.css'
})
export class Inicio {
  protected readonly userName = 'Brayan';

  protected readonly today = new Date().toLocaleDateString('es-CO', {
    day: 'numeric',
    month: 'long'
  });

  protected readonly stats: StatCard[] = [
    { label: 'Ventas hoy', value: '$8.450.000', trend: '↑ 12.3% vs ayer', trendPositive: true },
    { label: 'Viajes activos', value: '24', trend: 'En ruta ahora', trendPositive: true },
    { label: 'Usuarios', value: '1.248', trend: '↑ 8.7%', trendPositive: true },
    { label: 'Tiquetes vendidos', value: '856', trend: '↑ 15.3%', trendPositive: true }
  ];

  protected readonly weeklySales: WeeklySale[] = [
    { day: 'Lun', value: 45 },
    { day: 'Mar', value: 58 },
    { day: 'Mié', value: 50 },
    { day: 'Jue', value: 70 },
    { day: 'Vie', value: 92 },
    { day: 'Sáb', value: 63 },
    { day: 'Dom', value: 72 }
  ];

  protected readonly maxSaleValue = Math.max(...this.weeklySales.map((s) => s.value));

  protected readonly recentActivity: ActivityItem[] = [
    { icon: 'trip', title: 'Nuevo viaje creado — Bogotá → San Gil', subtitle: 'por Brayan Rada' },
    { icon: 'ticket', title: 'Tiquete vendido — TKT-0125', subtitle: 'Bogotá → Villa de Leyva' },
    { icon: 'driver', title: 'Conductor asignado — Carlos Pérez', subtitle: 'Bogotá → Barichara' }
  ];
}
