import { Component } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { HttpClient } from '@angular/common/http';
import { Router } from '@angular/router';

@Component({
  imports: [FormsModule, CommonModule],
  selector: 'app-login',
  styleUrl: './login.css',
  templateUrl: './login.html',
})
export class Login {
  rol: 'agencia' | 'super' = 'agencia';
  recordarme = false;
  mostrarContrasena = false;
  errorMensaje = '';

  usuario = {
    correo: '',
    contrasena: ''
  };

  constructor(private http: HttpClient, private router: Router) {}

  login() {
  this.errorMensaje = '';

  if (!this.usuario.correo && !this.usuario.contrasena) {
    this.errorMensaje = 'Ingresa tu correo y contraseña.';
    return;
  } else if (!this.usuario.correo) {
    this.errorMensaje = 'Ingresa tu correo electrónico.';
    return;
  } else if (!this.usuario.contrasena) {
    this.errorMensaje = 'Ingresa tu contraseña.';
    return;
  }

  this.http.post('http://127.0.0.1:8000/api/login/', { ...this.usuario, rol: this.rol })
    .subscribe({
      next: (respuesta: any) => {
        if (respuesta.token) {
          localStorage.setItem('token', respuesta.token);
          this.router.navigate(['/inicio']);
        } else {
          this.errorMensaje = 'No se pudo iniciar sesión. Intenta de nuevo.';
        }
      },
      error: (err) => {
        console.error('Error de login', err);

        if (err.status === 401 || err.status === 400) {
          this.errorMensaje = 'Correo o contraseña incorrectos.';
        } else if (err.status === 0) {
          this.errorMensaje = 'No se pudo conectar con el servidor.';
        } else {
          this.errorMensaje = 'Ocurrió un error. Intenta de nuevo más tarde.';
        }
      }
    });
}
}
