import { NgModule } from '@angular/core';
import { BrowserModule } from '@angular/platform-browser';
import {FormsModule} from "@angular/forms"
import { AppRoutingModule } from './app-routing.module';
import { AppComponent } from './app.component';
import { RouterModule } from '@angular/router';
import { MainRoutes } from '../Routing/App.routing';
import { Baselogger, consoleLogger, Dblogger, Filelogger } from '../Utility/app.Logger';
var provider=[
  //Centralized Dependancy Injection
  {provide:Baselogger,useClass:consoleLogger},
  //Condition Dependancy Injection
  {provide:'1',useClass:Dblogger},
  {provide:'2',useClass:Filelogger}]
@NgModule({
  declarations: [
    AppComponent,
  ],
  imports: [
    BrowserModule,
    AppRoutingModule,
    FormsModule,
    RouterModule.forRoot(MainRoutes),

  ],
  providers: [provider],
  bootstrap: [AppComponent]
})
export class AppModule { }
