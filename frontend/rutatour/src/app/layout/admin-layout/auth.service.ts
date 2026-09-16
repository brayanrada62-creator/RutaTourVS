import { Injectable } from '@angular/core';
import { HttpClient, HttpHeaders } from '@angular/common/http';
import { Observable } from 'rxjs';

export interface CurrentUser {
  name: string;
  role: string;
}

@Injectable({
  providedIn: 'root'
})
export class AuthService {
  private readonly apiUrl = 'http://127.0.0.1:8000/api';

  constructor(private http: HttpClient) {}

  getCurrentUser(): Observable<CurrentUser> {
    const token = localStorage.getItem('token');
    const headers = new HttpHeaders(
      token ? { Authorization: `Token ${token}` } : {}
    );
    return this.http.get<CurrentUser>(`${this.apiUrl}/usuario/perfil/`, { headers });
  }
}