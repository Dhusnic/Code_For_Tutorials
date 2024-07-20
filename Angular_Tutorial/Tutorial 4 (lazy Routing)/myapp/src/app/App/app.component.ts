import { Component } from '@angular/core';
import {Costumer} from './app.model'
@Component({
  selector: 'app-root',
  templateUrl: './app.component.html',
  styleUrls: ['./app.component.css']
})
export class AppComponent {
  title = 'myapp';
  CustomerModel : Costumer=new Costumer();
  CustomerModels:Array<Costumer>=new Array<Costumer>();
  Add()
  {
     this.CustomerModels.push(this.CustomerModel);
     this.CustomerModel=new Costumer();
  }
  Delete()
  {
    this.CustomerModels.pop();
  }

}
