import { Component, ChangeDetectorRef, OnInit } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';

interface Usuario {
  id: number;
  nombre_completo: string;
  correo: string;
  rol_id: number;
  telefono: string;
  password?: string;
}

@Component({
  selector: 'app-usuarios',
  imports: [CommonModule, FormsModule],
  templateUrl: './usuarios.html',
  styleUrl: './usuarios.css'
})
export class Usuarios implements OnInit {
  usuarios: Usuario[] = [];
  cargando = true;
  error = '';

  private apiUrl = 'http://127.0.0.1:8000/api/usuario/';

  mostrarModal = false;
  usuarioEnEdicion: Usuario | null = null;
  formUsuario: Partial<Usuario> = {};

  constructor(
    private http: HttpClient,
    private cdr: ChangeDetectorRef
  ) {}

  ngOnInit(): void {
    this.traerUsuarios();
  }

  traerUsuarios() {
    this.cargando = true;
    this.http.get<Usuario[]>(this.apiUrl)
      .subscribe({
        next: (respuesta) => {
          console.log(respuesta);
          this.usuarios = respuesta;
          this.cargando = false;
          this.cdr.detectChanges();
        },
        error: (err) => {
          console.log(err);
          this.error = 'No fue posible cargar los usuarios.';
          this.cargando = false;
          this.cdr.detectChanges();
        }
      });
  }

  abrirModalNuevo(): void {
    this.usuarioEnEdicion = null;
    this.formUsuario = { nombre_completo: '', correo: '', telefono: '', rol_id: undefined, password: '' };
    this.mostrarModal = true;
  }

  abrirModalEditar(usuario: Usuario): void {
    this.usuarioEnEdicion = usuario;
    this.formUsuario = { ...usuario, password: '' };
    this.mostrarModal = true;
  }

  cerrarModal(): void {
    this.mostrarModal = false;
    this.usuarioEnEdicion = null;
    this.error = '';
  }

  guardarUsuario(): void {
    if (this.usuarioEnEdicion) {
      // Actualizar (PUT sobre el detalle del usuario)
      this.http.put<Usuario>(`${this.apiUrl}${this.usuarioEnEdicion.id}/`, this.formUsuario)
        .subscribe({
          next: () => {
            this.traerUsuarios();
            this.cerrarModal();
          },
          error: (err) => {
            console.log(err);
            this.error = 'No se pudo actualizar el usuario.';
            this.cdr.detectChanges();
          }
        });
    } else {
      // Crear
      this.http.post<Usuario>(this.apiUrl, this.formUsuario)
        .subscribe({
          next: () => {
            this.traerUsuarios();
            this.cerrarModal();
          },
          error: (err) => {
            console.log(err);
            this.error = 'No se pudo crear el usuario.';
            this.cdr.detectChanges();
          }
        });
    }
  }

  confirmarEliminar(usuario: Usuario): void {
    if (!confirm(`¿Eliminar a ${usuario.nombre_completo}?`)) {
      return;
    }
    this.http.delete(`${this.apiUrl}${usuario.id}/`)
      .subscribe({
        next: () => this.traerUsuarios(),
        error: (err) => {
          console.log(err);
          this.error = 'No se pudo eliminar el usuario.';
          this.cdr.detectChanges();
        }
      });
  }

  // Descomenta esto cuando confirmes que el backend tiene un campo "activo":
  //
  // toggleActivo(usuario: Usuario): void {
  //   this.http.patch(`${this.apiUrl}${usuario.id}/`, { activo: !usuario.activo })
  //     .subscribe({
  //       next: () => {
  //         usuario.activo = !usuario.activo;
  //         this.cdr.detectChanges();
  //       },
  //       error: (err) => {
  //         console.log(err);
  //         this.error = 'No se pudo cambiar el estado del usuario.';
  //         this.cdr.detectChanges();
  //       }
  //     });
  // }
}