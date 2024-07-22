import { Component,Injector } from '@angular/core';
import {Supplier} from './Supplier.model';
import { Baselogger } from "../Utility/app.Logger";
@Component({
  templateUrl: './Supplier.component.html',
  styleUrls: ['./Supplier.component.css']
})
export class SupplierComp {
  title = 'myapp';
  CustomerModel : Supplier=new Supplier();
  CustomerModels:Array<Supplier>=new Array<Supplier>();
  logobj:Baselogger;
  //Tight Coupling
  // constructor()
  // {
  //   this.logobj=new Filelogger();
  //   this.logobj.log();
  // }

  //Lose Coupling

  //Centralized DI
  // constructor(logger:Baselogger)
  // {
  //   this.logobj=logger;
  //   this.logobj.log();
  // }


  //Conditional DI
  constructor(logger:Injector) {
    this.logobj = logger.get("2");
    this.logobj.log();
  }
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
