import { Component } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';

interface Bus {
  id: number;
  placa: string;
  modelo: string;
  capacidad: number;
  estado: 'Disponible' | 'En ruta' | 'Mantenimiento';
}

@Component({
  selector: 'app-buses',
  standalone: true,
  imports: [CommonModule, FormsModule],
  templateUrl: './buses.html',
  styleUrls: ['./buses.css']
})
export class BusesComponent {

  terminoBusqueda: string = '';

  // Datos de ejemplo. Más adelante los reemplazamos por la llamada a tu API de Django.
  buses: Bus[] = [
    { id: 1, placa: 'BES-123', modelo: 'Marcopolo G7', capacidad: 48, estado: 'Disponible' },
    { id: 2, placa: 'TUX-456', modelo: 'Scania K360', capacidad: 45, estado: 'En ruta' },
    { id: 3, placa: 'ABC-789', modelo: 'Mercedes Benz', capacidad: 38, estado: 'Mantenimiento' },
    { id: 4, placa: 'DEF-012', modelo: 'Volvo 9800', capacidad: 42, estado: 'Disponible' },
  ];

  get busesFiltrados(): Bus[] {
    if (!this.terminoBusqueda.trim()) {
      return this.buses;
    }
    const termino = this.terminoBusqueda.toLowerCase();
    return this.buses.filter(b =>
      b.placa.toLowerCase().includes(termino) ||
      b.modelo.toLowerCase().includes(termino)
    );
  }

  // Devuelve la clase CSS según el estado, para pintar el badge del color correcto
  claseEstado(estado: Bus['estado']): string {
    switch (estado) {
      case 'Disponible': return 'badge-disponible';
      case 'En ruta': return 'badge-en-ruta';
      case 'Mantenimiento': return 'badge-mantenimiento';
    }
  }
}