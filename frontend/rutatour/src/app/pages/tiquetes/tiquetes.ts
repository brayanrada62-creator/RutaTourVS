import { Component } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';

interface Tiquete {
  id: number;
  codigo: string;
  usuario: string;
  viaje: string;
  estado: 'Vendido'| 'Cancelado';
  total: number;
}

@Component({
  selector: 'app-tiquetes',
  standalone: true,
  imports: [CommonModule, FormsModule],
  templateUrl: './tiquetes.html',
  styleUrls: ['./tiquetes.css']
})
export class TiquetesComponent {

  terminoBusqueda: string = '';

  // Datos de ejemplo. Más adelante los reemplazamos por la llamada a tu API de Django.
  tiquetes: Tiquete[] = [
    { id: 1, codigo: 'TKT-0125', usuario: 'Daniela R.', viaje: 'Bta → Villa de Leyva', estado: 'Vendido', total: 45000 },
    { id: 2, codigo: 'TKT-0124', usuario: 'Juan P.', viaje: 'Bta → Barichara', estado: 'Vendido', total: 55000 },
    { id: 3, codigo: 'TKT-0123', usuario: 'Maria G.', viaje: 'Bta → Guatapé', estado: 'Cancelado', total: 50000 },
    { id: 4, codigo: 'TKT-0122', usuario: 'Oscar L.', viaje: 'Bta → Sta. Marta', estado: 'Vendido', total: 95000 },
  ];

  get tiquetesFiltrados(): Tiquete[] {
    if (!this.terminoBusqueda.trim()) {
      return this.tiquetes;
    }
    const termino = this.terminoBusqueda.toLowerCase();
    return this.tiquetes.filter(t =>
      t.codigo.toLowerCase().includes(termino) ||
      t.usuario.toLowerCase().includes(termino)
    );
  }

  formatearTotal(total: number): string {
    return '$' + total.toLocaleString('es-CO');
  }
}