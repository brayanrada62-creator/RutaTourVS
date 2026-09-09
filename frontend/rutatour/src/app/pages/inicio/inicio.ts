import { Component, OnInit } from '@angular/core';
import { DashboardService, StatCard, WeeklySale, ActivityItem } from './dashboard.service';

@Component({
  selector: 'app-inicio',
  imports: [],
  templateUrl: './inicio.html',
  styleUrl: './inicio.css'
})
export class Inicio implements OnInit {
  protected userName = '';

  protected readonly today = new Date().toLocaleDateString('es-CO', {
    day: 'numeric',
    month: 'long'
  });

  protected stats: StatCard[] = [];

  protected weeklySales: WeeklySale[] = [];

  protected maxSaleValue = 0;

  protected recentActivity: ActivityItem[] = [];

  constructor(private dashboardService: DashboardService) {}

  ngOnInit(): void {
    this.dashboardService.getUserName().subscribe({
      next: (res) => (this.userName = res.userName),
      error: () => (this.userName = '')
    });

    this.dashboardService.getStats().subscribe({
      next: (data) => (this.stats = data),
      error: () => (this.stats = [])
    });

    this.dashboardService.getWeeklySales().subscribe({
      next: (data) => {
        this.weeklySales = data;
        this.maxSaleValue = data.length ? Math.max(...data.map((s) => s.value)) : 0;
      },
      error: () => {
        this.weeklySales = [];
        this.maxSaleValue = 0;
      }
    });

    this.dashboardService.getRecentActivity().subscribe({
      next: (data) => (this.recentActivity = data),
      error: () => (this.recentActivity = [])
    });
  }
}