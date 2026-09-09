import { Component } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';

interface Viaje {
  id: number;
  ruta: string;
  origen: string;
  destino: string;
  horario: string;
  precio: number;
  estado: 'Activo' | 'Inactivo';
}

@Component({
  selector: 'app-viajes',
  standalone: true,
  imports: [CommonModule, FormsModule],
  templateUrl: './viajes.html',
  styleUrls: ['./viajes.css']
})
export class ViajesComponent {

  terminoBusqueda: string = '';

  pestanas: string[] = ['Información', 'Horarios', 'Precios', 'Paradas', 'Asignación'];
  pestanaActiva: string = 'Información';

  // Datos de ejemplo. Más adelante los reemplazamos por la llamada a tu API de Django.
  viajes: Viaje[] = [
    { id: 1, ruta: 'Bogotá → Villa de Leyva', origen: 'Bogotá, Terminal Salitre', destino: 'Villa de Leyva, Boyacá', horario: '07:00 AM', precio: 45000, estado: 'Activo' },
    { id: 2, ruta: 'Bogotá → Barichara', origen: 'Bogotá, Terminal Salitre', destino: 'Barichara, Santander', horario: '08:00 AM', precio: 55000, estado: 'Activo' },
    { id: 3, ruta: 'Bogotá → Guatapé', origen: 'Bogotá, Terminal Salitre', destino: 'Guatapé, Antioquia', horario: '09:00 AM', precio: 50000, estado: 'Activo' },
    { id: 4, ruta: 'Bogotá → Santa Marta', origen: 'Bogotá, Terminal Salitre', destino: 'Santa Marta, Magdalena', horario: '10:00 AM', precio: 95000, estado: 'Inactivo' },
    { id: 5, ruta: 'Bogotá → San Gil', origen: 'Bogotá, Terminal Salitre', destino: 'San Gil, Santander', horario: '11:00 AM', precio: 60000, estado: 'Activo' },
  ];

  viajeSeleccionado: Viaje = this.viajes[0];

  seleccionarViaje(viaje: Viaje): void {
    this.viajeSeleccionado = viaje;
    this.pestanaActiva = 'Información';
  }

  cambiarPestana(pestana: string): void {
    this.pestanaActiva = pestana;
  }

  get viajesFiltrados(): Viaje[] {
    if (!this.terminoBusqueda.trim()) {
      return this.viajes;
    }
    const termino = this.terminoBusqueda.toLowerCase();
    return this.viajes.filter(v => v.ruta.toLowerCase().includes(termino));
  }

  formatearPrecio(precio: number): string {
    return '$' + precio.toLocaleString('es-CO');
  }
}