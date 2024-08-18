import { Component} from '@angular/core';
import {dataInterface, DataService} from '../data.service';
import { FormBuilder,FormGroup } from '@angular/forms';
@Component({
  selector: 'app-form',
  templateUrl: './form.component.html',
  styleUrl: './form.component.css'
})
export class FormComponent {
  data:dataInterface={text_input:"",bool_input:false,pdf_input:"",photo_input:"",csv_input:""}
  constructor(private dataService:DataService,private fb:FormBuilder){
  }
  onPdfFileSelected(event:any)
  {
    const file: File = event.target.files[0];
    if(file)
    {
      this.data.pdf_input=file;
    }
    console.log(file)
  }
  onPhotoFileSelected(event:any)
  {
    const file: File = event.target.files[0];
    if(file)
    {
      this.data.photo_input=file;
    }
    console.log(file)
  }
  onCSVSelected(event:any)
  {
    const file: File = event.target.files[0];
    if(file)
    {
      this.data.csv_input=file;
    }
    console.log(file)
  }
  // onSubmit():void{
  //   console.log(this.data);
  //   this.dataService.uploadData(this.data).subscribe(response=>console.log(response));
  // }

  onSubmit(){
    
    if (this.data.pdf_input && this.data.photo_input && this.data.csv_input) {
      const formData = new FormData();
      formData.append('text_input',this.data.text_input);
      formData.append('bool_input',this.data.bool_input.toString());
      formData.append('pdf_input', this.data.pdf_input);
      formData.append('photo_input', this.data.photo_input);
      formData.append('csv_input', this.data.csv_input);

      this.dataService.uploadData(formData).subscribe(
        response => console.log('Upload successful', response),
        error => console.error('Upload error', error)
      );
    } 
  }

}
