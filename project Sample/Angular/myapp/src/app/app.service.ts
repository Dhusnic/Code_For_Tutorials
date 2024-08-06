import { HttpClient } from '@angular/common/http';
import { Injectable } from '@angular/core';
import { Observable } from 'rxjs';
export interface person{
  id?:number;
  name:string;
  age:number;
}
@Injectable({
  providedIn: 'root'
})
export class AppService {
  private apiurl='http://127.0.0.1:8000/api/persons/'
  constructor(private http:HttpClient) { }
  getPersons():Observable<person[]>
  {
    return this.http.get<person[]>(this.apiurl);
  }
  addperson(person:person):Observable<person>
  {
    return this.http.post<person>(this.apiurl,person);
  }
  editperson(person:person):Observable<person>
  {
    return this.http.put<person>(`${this.apiurl}${person.id}/`,person)
  }
  deletePerson(id:number):Observable<void>
  {
    return this.http.delete<void>(`${this.apiurl}${id}/`)
  }
}
