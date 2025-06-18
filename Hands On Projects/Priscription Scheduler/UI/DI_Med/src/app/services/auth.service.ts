import { Injectable } from '@angular/core';
import { BehaviorSubject } from 'rxjs';
import { HttpClient } from '@angular/common/http';
import { catchError, map, tap } from 'rxjs/operators';
import { Observable, of } from 'rxjs';
import { environment } from '../../environments/environment';
@Injectable({
  providedIn: 'root'
})
export class AuthService {

  constructor(private http: HttpClient) {
    const storedLogin = localStorage.getItem('isLoggedIn');
    const storedUsername = localStorage.getItem('username');

    if (storedLogin === 'true' && storedUsername) {
      this.loggedIn.next(true);
      this.username.next(storedUsername);
    }

    const token = localStorage.getItem('auth_token');
    const user = localStorage.getItem('username');
    if (token && user) {
      this.loggedIn.next(true);
      this.username.next(user);
    }
  }
  private loggedIn = new BehaviorSubject<boolean>(false);
  private username = new BehaviorSubject<string | null>(null);

  isLoggedIn$ = this.loggedIn.asObservable();
  username$ = this.username.asObservable();


  login(username: string, password: string): Observable<boolean> {
    return this.http.post<any>(`${environment.apiBaseUrl}/login`, { username, password }).pipe(
      tap(res => {
        localStorage.setItem('auth_token', res.token);
        localStorage.setItem('refresh_token', res.refreshToken);
        localStorage.setItem('username', res.username);
        this.loggedIn.next(true);
        this.username.next(res.username);
      }),
      map(() => true),
      catchError(() => of(false))
    );
  }


  logout() {
    localStorage.removeItem('auth_token');
    localStorage.removeItem('refresh_token');
    localStorage.removeItem('username');
    this.loggedIn.next(false);
    this.username.next(null);
  }

  getAccessToken(): string | null {
    return localStorage.getItem('auth_token');
  }

  getRefreshToken(): string | null {
    return localStorage.getItem('refresh_token');
  }

  refreshToken(refreshToken: string): Observable<string> {
  return this.http.post<{ token: string }>(`${environment.apiBaseUrl}/refresh-token`, { refreshToken }).pipe(
    tap(res => {
      localStorage.setItem('auth_token', res.token);
    }),
    map(res => res.token),
    catchError(() => {
      this.logout();
      return of('');
    })
  );
}

}
