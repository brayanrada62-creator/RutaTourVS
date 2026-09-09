import { Injectable } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable } from 'rxjs';

export interface StatCard {
  label: string;
  value: string;
  trend: string;
  trendPositive: boolean;
}

export interface WeeklySale {
  day: string;
  value: number;
}

export interface ActivityItem {
  icon: 'trip' | 'ticket' | 'driver';
  title: string;
  subtitle: string;
}

export interface DashboardData {
  userName: string;
  stats: StatCard[];
  weeklySales: WeeklySale[];
  recentActivity: ActivityItem[];
}

@Injectable({
  providedIn: 'root'
})
export class DashboardService {
  // TODO: reemplaza esta URL base por la de tu API real (Django REST, etc.)
  private readonly apiUrl = '/api';

  constructor(private http: HttpClient) {}

  // Nombre del usuario logueado (o tráelo de tu servicio de auth si ya lo tienes)
  getUserName(): Observable<{ userName: string }> {
    return this.http.get<{ userName: string }>(`${this.apiUrl}/usuario/perfil/`);
  }

  // Tarjetas de métricas superiores (ventas, viajes activos, usuarios, tiquetes, etc.)
  getStats(): Observable<StatCard[]> {
    return this.http.get<StatCard[]>(`${this.apiUrl}/dashboard/stats/`);
  }

  // Datos de la gráfica de venta semanal
  getWeeklySales(): Observable<WeeklySale[]> {
    return this.http.get<WeeklySale[]>(`${this.apiUrl}/dashboard/ventas-semanales/`);
  }

  // Actividad reciente (viajes, tiquetes, conductores asignados)
  getRecentActivity(): Observable<ActivityItem[]> {
    return this.http.get<ActivityItem[]>(`${this.apiUrl}/dashboard/actividad-reciente/`);
  }
}