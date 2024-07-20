import { NgModule } from '@angular/core';
import { CommonModule} from '@angular/common';
import {FormsModule} from "@angular/forms"
import { ContactComp } from "../Contact/Contact.component";
import { RouterModule } from '@angular/router';
import { MainRoutes } from '../Routing/Contact.routing';
@NgModule({
  declarations: [
    ContactComp,
  ],
  imports: [
    CommonModule,
    FormsModule,
    RouterModule.forChild(MainRoutes),

  ],
  providers: [],
  bootstrap: [ContactComp]
})
export class ContactModule { }
