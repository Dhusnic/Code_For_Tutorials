import { NgModule } from '@angular/core';
import { BrowserModule } from '@angular/platform-browser';
import {FormsModule} from "@angular/forms"
import { RouterModule } from '@angular/router';
import { MainRoutes } from '../Routing/App.routing';
import { HomeComp } from "./Home.component";
import { AppComponent } from "../App/app.component";
@NgModule({
  declarations: [
    AppComponent,
    HomeComp,
  ],
  imports: [
    BrowserModule,
    FormsModule,
    RouterModule.forChild(MainRoutes),

  ],
  providers: [],
  bootstrap: [AppComponent]
})
export class HomeModule { }
