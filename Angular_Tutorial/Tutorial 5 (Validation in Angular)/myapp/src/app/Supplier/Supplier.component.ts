import { Component } from '@angular/core';
import {Supplier} from './Supplier.model'
@Component({
  templateUrl: './Supplier.component.html',
  styleUrls: ['./Supplier.component.css']
})
export class SupplierComp {
  title = 'myapp';
  CustomerModel : Supplier=new Supplier();
  CustomerModels:Array<Supplier>=new Array<Supplier>();
  Add()
  {
     this.CustomerModels.push(this.CustomerModel);
     this.CustomerModel=new Supplier();
  }
  Delete()
  {
    this.CustomerModels.pop();
  }
  hasError(typeofvalidator:string,controlename:string):boolean
  {
    return this.CustomerModel.formCustomerGroup.controls[controlename].hasError(typeofvalidator);
  }

}
