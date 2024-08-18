import { Component } from '@angular/core';
import {DataService} from '../data.service';
import {Papa} from 'ngx-papaparse';
@Component({
  selector: 'app-csv-form',
  templateUrl: './csv-form.component.html',
  styleUrl: './csv-form.component.css'
})
export class CsvFormComponent {
  constructor(private DataService:DataService,private papa: Papa) {}
    downloadeCSV()
    {
      this.DataService.downloadeCSV().subscribe(response=>{
        console.log("Downloade Successfull")
        const url=window.URL.createObjectURL(response)
        const a = document.createElement('a');
        a.href = url;
        a.download = 'Data.csv';  // You can set a custom filename here
        a.click();
        window.URL.revokeObjectURL(url);
      })
  }
  onFileChange(event: any) {
    const file = event.target.files[0];
    if (file) {
      this.papa.parse(file, {
        complete: (result) => {
          const data = result.data;
          this.DataService.uploadCSV(data).subscribe(response => {
            console.log('Data successfully uploaded', response);
          });
        },
        header: true // Assumes the first row is the header
      });
    }
  }
}
