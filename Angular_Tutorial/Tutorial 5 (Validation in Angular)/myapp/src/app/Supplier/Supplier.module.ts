import { NgModule } from '@angular/core';
import { CommonModule } from '@angular/common';
import {FormsModule,ReactiveFormsModule} from "@angular/forms"
import {SupplierComp} from "../Supplier/Supplier.component";
import { RouterModule } from '@angular/router';
import { MainRoutes } from '../Routing/Supplier.routing';
@NgModule({
  declarations: [
    SupplierComp,
  ],
  imports: [
    CommonModule,
    FormsModule,
    RouterModule.forChild(MainRoutes),
    ReactiveFormsModule,

  ],
  providers: [],
  bootstrap: [SupplierComp]
})
export class SupplierModule { }
