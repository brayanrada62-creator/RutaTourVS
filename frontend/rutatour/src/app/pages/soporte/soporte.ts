import { Component } from '@angular/core';
import { CommonModule } from '@angular/common';

interface OpcionSoporte {
  titulo: string;
  descripcion: string;
  icono: string; // usamos un string simple para identificar qué ícono mostrar
}

@Component({
  selector: 'app-soporte',
  standalone: true,
  imports: [CommonModule],
  templateUrl: './soporte.html',
  styleUrls: ['./soporte.css']
})
export class SoporteComponent {

  opciones: OpcionSoporte[] = [
    { titulo: 'Novedades de viaje', descripcion: 'Ver solicitudes', icono: 'bus' },
    { titulo: 'Quejas y reclamos', descripcion: 'Ver solicitudes', icono: 'alerta' },
    { titulo: 'Solicitudes de usuario', descripcion: 'Ver solicitudes', icono: 'usuarios' },
    { titulo: 'Centro de ayuda', descripcion: 'Ir al centro', icono: 'audifonos' },
  ];

  telefono: string = '+57 320 123 4567';
  horario: string = 'Lun – Dom: 6:00 AM a 10:00 PM';

  abrirOpcion(opcion: OpcionSoporte): void {
    // Por ahora solo lo dejamos preparado; aquí luego puedes navegar
    // a la pantalla correspondiente o abrir un modal.
    console.log('Abrir sección:', opcion.titulo);
  }
}