import { Injectable } from '@angular/core';
import { HttpClient,HttpHeaders } from "@angular/common/http";
import { from, Observable } from 'rxjs';
export interface dataInterface{
  id?:number,
  text_input:string,
  bool_input:boolean,
  pdf_input:File|any,
  photo_input:File|any,
  csv_input:File|any,
}

@Injectable({
  providedIn: 'root'
})
export class DataService {
  private apiurl='http://127.0.0.1:8000/api/data'
  constructor(private http:HttpClient) { }
  uploadData(data:FormData):Observable<any>
  {
    return this.http.post('http://127.0.0.1:8000/api/data/data/',data);
  }
  getData():Observable<any[]>
  {
    return this.http.get<any[]>('http://127.0.0.1:8000/api/data/data/');
  }
  deleteData(id:number):Observable<any>{
    return this.http.delete<any[]>(`http://127.0.0.1:8000/api/data/data/${id}/`);  
  }
  downloadeCSV():Observable<Blob>
  {
    return this.http.get('http://127.0.0.1:8000/api/csv/downloade_csv',{responseType:'blob'})
  }
  uploadCSV(data:any):Observable<any>
  {
    return this.http.post("http://127.0.0.1:8000/api/csv/upload_csv",data)
  }
  
}
