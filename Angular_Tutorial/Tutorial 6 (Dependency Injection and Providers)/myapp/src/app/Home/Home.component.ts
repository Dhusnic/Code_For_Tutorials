import { Component, Injector } from '@angular/core';
import { Home } from './Home.model';
import { Filelogger, Baselogger } from '../Utility/app.Logger';
@Component({
  templateUrl: './Home.component.html',
  styleUrls: ['./Home.component.css'],
})
export class HomeComp {
  title = 'myapp';
  logobj: Baselogger;
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
    this.logobj = logger.get("1");
    this.logobj.log();
  }
}
