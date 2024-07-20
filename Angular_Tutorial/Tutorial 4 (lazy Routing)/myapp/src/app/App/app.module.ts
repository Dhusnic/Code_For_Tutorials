import { NgModule } from '@angular/core';
import { BrowserModule } from '@angular/platform-browser';
import {FormsModule} from "@angular/forms"
import { AppRoutingModule } from './app-routing.module';
import { AppComponent } from './app.component';
// import { ContactComp } from "../Contact/Contact.component";
// import { HomeComp} from "../Home/Home.component";
// import {SupplierComp} from "../Supplier/Supplier.component";
import { RouterModule } from '@angular/router';
import { MainRoutes } from '../Routing/App.routing';
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
  providers: [],
  bootstrap: [AppComponent]
})
export class AppModule { }
