import { Injectable } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable } from 'rxjs';

export interface CurrentUser {
  name: string;
  role: string;
}

@Injectable({
  providedIn: 'root'
})
export class AuthService {
  // TODO: reemplaza esta URL base por la de tu API real (Django REST, etc.)
  private readonly apiUrl = '/api';

  constructor(private http: HttpClient) {}

  // Usuario actualmente logueado (nombre y rol)
  getCurrentUser(): Observable<CurrentUser> {
    return this.http.get<CurrentUser>(`${this.apiUrl}/usuario/perfil/`);
  }
}