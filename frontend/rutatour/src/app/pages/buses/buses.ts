import { Component, ChangeDetectorRef, OnInit } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';

interface Bus {
  id: number;
  placa: string;
  modelo: string;
  capacidad: number;
}

@Component({
  selector: 'app-buses',
  imports: [CommonModule, FormsModule],
  templateUrl: './buses.html',
  styleUrl: './buses.css'
})
export class Buses implements OnInit {
  buses: Bus[] = [];
  cargando = true;
  error = '';

  private apiUrl = 'http://127.0.0.1:8000/api/bus/';

  mostrarModal = false;
  busEnEdicion: Bus | null = null;
  formBus: Partial<Bus> = {};

  constructor(
    private http: HttpClient,
    private cdr: ChangeDetectorRef
  ) {}

  ngOnInit(): void {
    this.traerBuses();
  }

  traerBuses(): void {
    this.cargando = true;
    this.http.get<Bus[]>(this.apiUrl)
      .subscribe({
        next: (respuesta) => {
          console.log(respuesta);
          this.buses = respuesta;
          this.cargando = false;
          this.cdr.detectChanges();
        },
        error: (err) => {
          console.log(err);
          this.error = 'No fue posible cargar los buses.';
          this.cargando = false;
          this.cdr.detectChanges();
        }
      });
  }

  abrirModalNuevo(): void {
    this.busEnEdicion = null;
    this.formBus = { placa: '', modelo: '', capacidad: undefined };
    this.mostrarModal = true;
  }

  abrirModalEditar(bus: Bus): void {
    this.busEnEdicion = bus;
    this.formBus = { ...bus };
    this.mostrarModal = true;
  }

  cerrarModal(): void {
    this.mostrarModal = false;
    this.busEnEdicion = null;
    this.error = '';
  }

  guardarBus(): void {
    if (this.busEnEdicion) {
      this.http.put<Bus>(`${this.apiUrl}${this.busEnEdicion.id}/`, this.formBus)
        .subscribe({
          next: () => {
            this.traerBuses();
            this.cerrarModal();
          },
          error: (err) => {
            console.log(err);
            this.error = 'No se pudo actualizar el bus.';
            this.cdr.detectChanges();
          }
        });
    } else {
      this.http.post<Bus>(this.apiUrl, this.formBus)
        .subscribe({
          next: () => {
            this.traerBuses();
            this.cerrarModal();
          },
          error: (err) => {
            console.log(err);
            this.error = 'No se pudo crear el bus.';
            this.cdr.detectChanges();
          }
        });
    }
  }

  confirmarEliminar(bus: Bus): void {
    if (!confirm(`¿Eliminar el bus con placa ${bus.placa}?`)) {
      return;
    }
    this.http.delete(`${this.apiUrl}${bus.id}/`)
      .subscribe({
        next: () => this.traerBuses(),
        error: (err) => {
          console.log(err);
          this.error = 'No se pudo eliminar el bus.';
          this.cdr.detectChanges();
        }
      });
  }
}