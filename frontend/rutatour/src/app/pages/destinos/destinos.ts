import { Component, ChangeDetectorRef, OnInit } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';

interface Destino {
  id: number;
  nombre: string;
  departamento: string;
  descripcion: string;
}

@Component({
  selector: 'app-destinos',
  imports: [CommonModule, FormsModule],
  templateUrl: './destinos.html',
  styleUrl: './destinos.css'
})
export class Destinos implements OnInit {
  destinos: Destino[] = [];
  cargando = true;
  error = '';

  private apiUrl = 'http://127.0.0.1:8000/api/destino/';

  mostrarModal = false;
  destinoEnEdicion: Destino | null = null;
  formDestino: Partial<Destino> = {};

  constructor(
    private http: HttpClient,
    private cdr: ChangeDetectorRef
  ) {}

  ngOnInit(): void {
    this.traerDestinos();
  }

  traerDestinos(): void {
    this.cargando = true;
    this.http.get<Destino[]>(this.apiUrl)
      .subscribe({
        next: (respuesta) => {
          console.log(respuesta);
          this.destinos = respuesta;
          this.cargando = false;
          this.cdr.detectChanges();
        },
        error: (err) => {
          console.log(err);
          this.error = 'No fue posible cargar los destinos.';
          this.cargando = false;
          this.cdr.detectChanges();
        }
      });
  }

  abrirModalNuevo(): void {
    this.destinoEnEdicion = null;
    this.formDestino = { nombre: '', departamento: '', descripcion: '' };
    this.mostrarModal = true;
  }

  abrirModalEditar(destino: Destino): void {
    this.destinoEnEdicion = destino;
    this.formDestino = { ...destino };
    this.mostrarModal = true;
  }

  cerrarModal(): void {
    this.mostrarModal = false;
    this.destinoEnEdicion = null;
    this.error = '';
  }

  guardarDestino(): void {
    if (this.destinoEnEdicion) {
      this.http.put<Destino>(`${this.apiUrl}${this.destinoEnEdicion.id}/`, this.formDestino)
        .subscribe({
          next: () => {
            this.traerDestinos();
            this.cerrarModal();
          },
          error: (err) => {
            console.log(err);
            this.error = 'No se pudo actualizar el destino.';
            this.cdr.detectChanges();
          }
        });
    } else {
      this.http.post<Destino>(this.apiUrl, this.formDestino)
        .subscribe({
          next: () => {
            this.traerDestinos();
            this.cerrarModal();
          },
          error: (err) => {
            console.log(err);
            this.error = 'No se pudo crear el destino.';
            this.cdr.detectChanges();
          }
        });
    }
  }

  confirmarEliminar(destino: Destino): void {
    if (!confirm(`¿Eliminar el destino "${destino.nombre}"?`)) {
      return;
    }
    this.http.delete(`${this.apiUrl}${destino.id}/`)
      .subscribe({
        next: () => this.traerDestinos(),
        error: (err) => {
          console.log(err);
          this.error = 'No se pudo eliminar el destino.';
          this.cdr.detectChanges();
        }
      });
  }
}