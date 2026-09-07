import { Component } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { HttpClient } from '@angular/common/http';
import { Router } from '@angular/router';

@Component({
  imports: [FormsModule],
  selector: 'app-login',
  styleUrl: './login.css',
  templateUrl: './login.html',
})
export class Login {
usuario={
  correo:'',
  contrasena:''
}
  constructor(private http: HttpClient,
    private router: Router
  ) {}
  login(){
    this.http.post('http://127.0.0.1:8000/api/login/',
      this.usuario).subscribe((respuesta:any)=>{
        if (respuesta.token) {
          this.router.navigate(['/inicio']);
        }
      });
  }
}
