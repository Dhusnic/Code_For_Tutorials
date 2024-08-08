import { Component,OnInit } from '@angular/core';
import {DataService} from '../data.service';
@Component({
  selector: 'app-form',
  templateUrl: './form.component.html',
  styleUrl: './form.component.css'
})
export class FormComponent {
  data:any[]=[];
  constructor(private dataService:DataService){}
  ngOnInit(){
    //Called after the constructor, initializing input properties, and the first call to ngOnChanges.
    //Add 'implements OnInit' to the class.
    this.dataService.getData().subscribe(response=>{this.data=response});
  }
}
