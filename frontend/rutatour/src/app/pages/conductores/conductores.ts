import { Component, ChangeDetectorRef, OnInit } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';

interface Usuario {
  id: number;
  nombre_completo: string;
  agencia_id: number;
  rol_id: number;
  tipo_documento: string;
  numero_documento: string;
  correo: string;
  telefono: string;
  contrasena?: string;
}

@Component({
  selector: 'app-conductores',
  imports: [CommonModule, FormsModule],
  templateUrl: './conductores.html',
  styleUrl: './conductores.css'
})
export class Conductores implements OnInit {
  // TODO: ajusta este valor al ID real del rol "conductor" en tu tabla `roles`.
  // Mientras no exista un endpoint de Rol, este ID queda fijo aqui.
  private readonly ROL_CONDUCTOR_ID = 3;

  conductores: Usuario[] = [];
  cargando = true;
  error = '';

  private apiUrl = 'http://127.0.0.1:8000/api/usuario/';

  mostrarModal = false;
  conductorEnEdicion: Usuario | null = null;
  formConductor: Partial<Usuario> = {};

  constructor(
    private http: HttpClient,
    private cdr: ChangeDetectorRef
  ) {}

  ngOnInit(): void {
    this.traerConductores();
  }

  traerConductores(): void {
    this.cargando = true;
    this.http.get<Usuario[]>(this.apiUrl)
      .subscribe({
        next: (respuesta) => {
          console.log(respuesta);
          // Filtramos en el frontend: solo usuarios con rol de conductor.
          this.conductores = respuesta.filter(u => u.rol_id === this.ROL_CONDUCTOR_ID);
          this.cargando = false;
          this.cdr.detectChanges();
        },
        error: (err) => {
          console.log(err);
          this.error = 'No fue posible cargar los conductores.';
          this.cargando = false;
          this.cdr.detectChanges();
        }
      });
  }

  abrirModalNuevo(): void {
    this.conductorEnEdicion = null;
    this.formConductor = {
      nombre_completo: '',
      agencia_id: undefined,
      rol_id: this.ROL_CONDUCTOR_ID,
      tipo_documento: '',
      numero_documento: '',
      correo: '',
      telefono: '',
      contrasena: ''
    };
    this.mostrarModal = true;
  }

  abrirModalEditar(conductor: Usuario): void {
    this.conductorEnEdicion = conductor;
    this.formConductor = { ...conductor, contrasena: '' };
    this.mostrarModal = true;
  }

  cerrarModal(): void {
    this.mostrarModal = false;
    this.conductorEnEdicion = null;
    this.error = '';
  }

  guardarConductor(): void {
    // Forzamos siempre el rol de conductor, sin importar lo que traiga el formulario.
    this.formConductor.rol_id = this.ROL_CONDUCTOR_ID;

    if (this.conductorEnEdicion) {
      this.http.put<Usuario>(`${this.apiUrl}${this.conductorEnEdicion.id}/`, this.formConductor)
        .subscribe({
          next: () => {
            this.traerConductores();
            this.cerrarModal();
          },
          error: (err) => {
            console.log(err);
            this.error = 'No se pudo actualizar el conductor.';
            this.cdr.detectChanges();
          }
        });
    } else {
      this.http.post<Usuario>(this.apiUrl, this.formConductor)
        .subscribe({
          next: () => {
            this.traerConductores();
            this.cerrarModal();
          },
          error: (err) => {
            console.log(err);
            this.error = 'No se pudo crear el conductor.';
            this.cdr.detectChanges();
          }
        });
    }
  }

  confirmarEliminar(conductor: Usuario): void {
    if (!confirm(`¿Eliminar al conductor ${conductor.nombre_completo}?`)) {
      return;
    }
    this.http.delete(`${this.apiUrl}${conductor.id}/`)
      .subscribe({
        next: () => this.traerConductores(),
        error: (err) => {
          console.log(err);
          this.error = 'No se pudo eliminar el conductor.';
          this.cdr.detectChanges();
        }
      });
  }
}
