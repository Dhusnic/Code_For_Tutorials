import { Component,Injector } from '@angular/core';
import {Contact} from './Contact.model';
import { Baselogger, Filelogger } from "../Utility/app.Logger";
@Component({
  templateUrl: './Contact.component.html',
  styleUrls: ['./Contact.component.css']
})
export class ContactComp {
  title = 'myapp';
  logobj:Baselogger;
//Tight Coupling
  // constructor()
  // {
  //   this.logobj=new Filelogger();
  //   this.logobj.log();
  // }

  //Lose Coupling

  //Centralized DI
  constructor(logger:Baselogger)
  {
    this.logobj=logger;
    this.logobj.log();
  }


  //Conditional DI
  // constructor(logger:Injector) {
  //   this.logobj = logger.get(1);
  //   this.logobj.log();
  // }
}
