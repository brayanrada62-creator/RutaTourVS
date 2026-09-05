import { Component } from '@angular/core';
import { CommonModule } from '@angular/common';
import { Sidebar } from '../../shared/sidebar/sidebar';
import { Topbar } from '../../shared/topbar/topbar';

interface ReportCard {
  icon: 'chart' | 'bus' | 'map' | 'file';
  title: string;
  subtitle: string;
}

@Component({
  selector: 'app-reports',
  standalone: true,
  imports: [CommonModule, Sidebar, Topbar],
  templateUrl: './reports.html',
  styleUrl: './reports.css'
})
export class Reports {
  // TODO: este valor debe salir del selector de rango de fechas (y/o de lo que el
  // usuario elija), y usarse para pedirle al backend las estadísticas de ese periodo.
  dateRange = '';

  // Estas tarjetas son las opciones de reporte disponibles (no son datos de la
  // base de datos, son la navegación de la pantalla).
  reportCards: ReportCard[] = [
    { icon: 'chart', title: 'Ventas por agencia', subtitle: 'Ver reporte detallado' },
    { icon: 'bus', title: 'Viajes totales', subtitle: 'Ver reporte detallado' },
    { icon: 'map', title: 'Ocupación promedio', subtitle: 'Ver reporte detallado' },
    { icon: 'file', title: 'Comparativo de agencias', subtitle: 'Ver reporte detallado' }
  ];
}