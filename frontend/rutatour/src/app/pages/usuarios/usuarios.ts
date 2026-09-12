import { Component } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';

interface Usuario {
  id: number;
  correo: string;
  rol: string;
  estado: 'Activo' | 'Inactivo';
}

@Component({
  selector: 'app-usuarios',
  standalone: true,
  imports: [CommonModule, FormsModule],
  templateUrl: './usuarios.html',
  styleUrls: ['./usuarios.css']
})
export class UsuariosComponent {

  terminoBusqueda: string = '';

  // Datos de ejemplo. Más adelante los reemplazamos por la llamada a tu API de Django.
  usuarios: Usuario[] = [
    { id: 1, correo: 'admin@rutatour.com', rol: 'Administrador', estado: 'Activo' },
    { id: 2, correo: 'soporte@rutatour.com', rol: 'Soporte', estado: 'Activo' },
    { id: 3, correo: 'ventas@rutatour.com', rol: 'Vendedor', estado: 'Activo' },
    { id: 4, correo: 'operaciones@rutatour.com', rol: 'Operador', estado: 'Inactivo' },
  ];

  get usuariosFiltrados(): Usuario[] {
    if (!this.terminoBusqueda.trim()) {
      return this.usuarios;
    }
    const termino = this.terminoBusqueda.toLowerCase();
    return this.usuarios.filter(u =>
      u.correo.toLowerCase().includes(termino) ||
      u.rol.toLowerCase().includes(termino)
    );
  }
}