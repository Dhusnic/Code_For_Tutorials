import { Injectable } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable } from 'rxjs';
@Injectable({
  providedIn: 'root'
})
export class ApiService {
  private apiUrl="http://localhost:8000/auth/"
  constructor(private http: HttpClient) {}

  // Send form data to the API
  sign_up(data: any): Observable<any> {
    return this.http.post(`${this.apiUrl}sign_up/`, data);
  }
  log_in(data:any):Observable<any>
  {
    return this.http.post(`${this.apiUrl}login/`,data);
  }
  
}
