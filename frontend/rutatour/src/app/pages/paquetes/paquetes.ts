import { Component, ChangeDetectorRef, OnInit } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';

interface Paquete {
  id: number;
  nombre: string;
  agencia_id: number;
  descripcion: string;
  duracion_estimada: string;
  estado: string;
  fecha_creacion: string;
}

@Component({
  selector: 'app-paquetes',
  imports: [CommonModule, FormsModule],
  templateUrl: './paquetes.html',
  styleUrl: './paquetes.css'
})
export class Paquetes implements OnInit {
  paquetes: Paquete[] = [];
  cargando = true;
  error = '';

  private apiUrl = 'http://127.0.0.1:8000/api/paquete/';

  mostrarModal = false;
  paqueteEnEdicion: Paquete | null = null;
  formPaquete: Partial<Paquete> = {};

  estados = ['activo', 'inactivo', 'agotado'];

  constructor(
    private http: HttpClient,
    private cdr: ChangeDetectorRef
  ) {}

  ngOnInit(): void {
    this.traerPaquetes();
  }

  traerPaquetes(): void {
    this.cargando = true;
    this.http.get<Paquete[]>(this.apiUrl)
      .subscribe({
        next: (respuesta) => {
          console.log(respuesta);
          this.paquetes = respuesta;
          this.cargando = false;
          this.cdr.detectChanges();
        },
        error: (err) => {
          console.log(err);
          this.error = 'No fue posible cargar los paquetes.';
          this.cargando = false;
          this.cdr.detectChanges();
        }
      });
  }

  abrirModalNuevo(): void {
    this.paqueteEnEdicion = null;
    this.formPaquete = {
      nombre: '',
      agencia_id: undefined,
      descripcion: '',
      duracion_estimada: '',
      estado: 'activo',
      fecha_creacion: new Date().toISOString().substring(0, 10)
    };
    this.mostrarModal = true;
  }

  abrirModalEditar(paquete: Paquete): void {
    this.paqueteEnEdicion = paquete;
    this.formPaquete = { ...paquete };
    this.mostrarModal = true;
  }

  cerrarModal(): void {
    this.mostrarModal = false;
    this.paqueteEnEdicion = null;
    this.error = '';
  }

  guardarPaquete(): void {
    if (this.paqueteEnEdicion) {
      // Actualizar (PUT sobre el detalle del paquete)
      this.http.put<Paquete>(`${this.apiUrl}${this.paqueteEnEdicion.id}/`, this.formPaquete)
        .subscribe({
          next: () => {
            this.traerPaquetes();
            this.cerrarModal();
          },
          error: (err) => {
            console.log(err);
            this.error = 'No se pudo actualizar el paquete.';
            this.cdr.detectChanges();
          }
        });
    } else {
      // Crear
      this.http.post<Paquete>(this.apiUrl, this.formPaquete)
        .subscribe({
          next: () => {
            this.traerPaquetes();
            this.cerrarModal();
          },
          error: (err) => {
            console.log(err);
            this.error = 'No se pudo crear el paquete.';
            this.cdr.detectChanges();
          }
        });
    }
  }

  confirmarEliminar(paquete: Paquete): void {
    if (!confirm(`¿Eliminar el paquete "${paquete.nombre}"?`)) {
      return;
    }
    this.http.delete(`${this.apiUrl}${paquete.id}/`)
      .subscribe({
        next: () => this.traerPaquetes(),
        error: (err) => {
          console.log(err);
          this.error = 'No se pudo eliminar el paquete.';
          this.cdr.detectChanges();
        }
      });
  }
}