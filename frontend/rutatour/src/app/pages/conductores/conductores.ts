import { Component } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';

interface Conductor {
  id: number;
  nombre: string;
  licencia: string;
  telefono: string;
  estado: 'Activo' | 'Inactivo';
}

@Component({
  selector: 'app-conductores',
  standalone: true,
  imports: [CommonModule, FormsModule],
  templateUrl: './conductores.html',
  styleUrls: ['./conductores.css']
})
export class ConductoresComponent {

  terminoBusqueda: string = '';

  // Datos de ejemplo. Más adelante los reemplazamos por la llamada a tu API de Django.
  conductores: Conductor[] = [
    { id: 1, nombre: 'Carlos Pérez', licencia: 'C2 123456', telefono: '311 234 5678', estado: 'Activo' },
    { id: 2, nombre: 'Juana Rodríguez', licencia: 'C2 234567', telefono: '312 345 6789', estado: 'Activo' },
    { id: 3, nombre: 'Luis Martínez', licencia: 'C2 345678', telefono: '313 456 7890', estado: 'Inactivo' },
    { id: 4, nombre: 'Pedro Gómez', licencia: 'C2 456789', telefono: '314 567 8801', estado: 'Activo' },
  ];

  get conductoresFiltrados(): Conductor[] {
    if (!this.terminoBusqueda.trim()) {
      return this.conductores;
    }
    const termino = this.terminoBusqueda.toLowerCase();
    return this.conductores.filter(c => c.nombre.toLowerCase().includes(termino));
  }
}