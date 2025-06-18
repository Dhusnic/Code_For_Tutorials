import { NgModule } from '@angular/core';
import { CommonModule } from '@angular/common';
import { NavBarComponent } from './nav-bar/nav-bar.component';
import { CoreSidebarComponent } from './core-sidebar/core-sidebar.component';



@NgModule({
  declarations: [
    NavBarComponent,
    CoreSidebarComponent
  ],
  imports: [
    CommonModule
  ]
})
export class MainComponentModule { }
