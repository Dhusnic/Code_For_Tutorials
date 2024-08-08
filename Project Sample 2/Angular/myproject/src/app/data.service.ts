import { Injectable } from '@angular/core';
import { HttpClient } from "@angular/common/http";
import { from, Observable } from 'rxjs';


@Injectable({
  providedIn: 'root'
})
export class DataService {
  private apiurl='http://127.0.0.1:8000/api/data'
  constructor(private http:HttpClient) { }
  uploadData(data:FormData):Observable<any>
  {
    return this.http.put('http://127.0.0.1:8000/api/data/data',data);
  }
  getData():Observable<any>
  {
    return this.http.get('http://127.0.0.1:8000/api/data');
  }
  
}
