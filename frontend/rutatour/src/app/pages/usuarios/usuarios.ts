import { Component, ChangeDetectorRef, OnInit } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { CommonModule } from '@angular/common';

interface Usuario {
  id: number;
  nombre_completo: string;
  correo: string;
  rol_id: number;
  telefono: string;
}

@Component({
  selector: 'app-usuarios',
  imports: [CommonModule],
  templateUrl: './usuarios.html',
  styleUrl: './usuarios.css'
})
export class Usuarios implements OnInit {
  usuarios: Usuario[] = [];
  cargando = true;
  error = '';

  constructor(
    private http: HttpClient,
    private cdr: ChangeDetectorRef
  ) {}

  ngOnInit(): void {
    this.traerUsuarios();
  }

  traerUsuarios() {
    this.http.get<Usuario[]>('http://127.0.0.1:8000/api/usuario/')
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
}