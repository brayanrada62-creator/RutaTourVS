import { Component } from '@angular/core';
import { CommonModule } from '@angular/common';

@Component({
  selector: 'app-panel-administrativo',
  standalone: true,
  imports: [CommonModule],
  templateUrl: './panel-administrativo.html',
  styleUrls: ['./panel-administrativo.css']
})
export class PanelAdministrativo {

  // guarda qué sección está seleccionada en la barra lateral
  seccionActiva: string = '';

  // nombres bonitos para mostrar según la sección
  titulos: { [id: string]: string } = {
    inicio: 'Inicio',
    estadisticas: 'Estadísticas',
    'tiempo-real': 'Tiempo real',
    buses: 'Buses',
    conductores: 'Conductores',
    rutas: 'Rutas',
    reservas: 'Reservas',
    usuarios: 'Usuarios',
    soporte: 'Atención y soporte'
  };

  mostrarSeccion(id: string): void {
    this.seccionActiva = id;
  }
}