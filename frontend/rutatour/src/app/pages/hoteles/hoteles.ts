import { Component, ChangeDetectorRef, OnInit } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';

interface Hospedaje {
  id: number;
  nombre: string;
  destino_id: number;
  direccion: string;
  telefono: string;
  descripcion: string;
}

@Component({
  selector: 'app-hoteles',
  imports: [CommonModule, FormsModule],
  templateUrl: './hoteles.html',
  styleUrl: './hoteles.css'
})
export class Hoteles implements OnInit {
  hoteles: Hospedaje[] = [];
  cargando = true;
  error = '';

  // El backend llama a esta entidad "Hospedaje" (tabla hospedaje).
  private apiUrl = 'http://127.0.0.1:8000/api/hospedaje/';

  mostrarModal = false;
  hotelEnEdicion: Hospedaje | null = null;
  formHotel: Partial<Hospedaje> = {};

  constructor(
    private http: HttpClient,
    private cdr: ChangeDetectorRef
  ) {}

  ngOnInit(): void {
    this.traerHoteles();
  }

  traerHoteles(): void {
    this.cargando = true;
    this.http.get<Hospedaje[]>(this.apiUrl)
      .subscribe({
        next: (respuesta) => {
          console.log(respuesta);
          this.hoteles = respuesta;
          this.cargando = false;
          this.cdr.detectChanges();
        },
        error: (err) => {
          console.log(err);
          this.error = 'No fue posible cargar los hoteles.';
          this.cargando = false;
          this.cdr.detectChanges();
        }
      });
  }

  abrirModalNuevo(): void {
    this.hotelEnEdicion = null;
    this.formHotel = { nombre: '', destino_id: undefined, direccion: '', telefono: '', descripcion: '' };
    this.mostrarModal = true;
  }

  abrirModalEditar(hotel: Hospedaje): void {
    this.hotelEnEdicion = hotel;
    this.formHotel = { ...hotel };
    this.mostrarModal = true;
  }

  cerrarModal(): void {
    this.mostrarModal = false;
    this.hotelEnEdicion = null;
    this.error = '';
  }

  guardarHotel(): void {
    if (this.hotelEnEdicion) {
      this.http.put<Hospedaje>(`${this.apiUrl}${this.hotelEnEdicion.id}/`, this.formHotel)
        .subscribe({
          next: () => {
            this.traerHoteles();
            this.cerrarModal();
          },
          error: (err) => {
            console.log(err);
            this.error = 'No se pudo actualizar el hotel.';
            this.cdr.detectChanges();
          }
        });
    } else {
      this.http.post<Hospedaje>(this.apiUrl, this.formHotel)
        .subscribe({
          next: () => {
            this.traerHoteles();
            this.cerrarModal();
          },
          error: (err) => {
            console.log(err);
            this.error = 'No se pudo crear el hotel.';
            this.cdr.detectChanges();
          }
        });
    }
  }

  confirmarEliminar(hotel: Hospedaje): void {
    if (!confirm(`¿Eliminar el hotel "${hotel.nombre}"?`)) {
      return;
    }
    this.http.delete(`${this.apiUrl}${hotel.id}/`)
      .subscribe({
        next: () => this.traerHoteles(),
        error: (err) => {
          console.log(err);
          this.error = 'No se pudo eliminar el hotel.';
          this.cdr.detectChanges();
        }
      });
  }
}