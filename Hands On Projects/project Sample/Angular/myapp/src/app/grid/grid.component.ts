import { Component } from '@angular/core';
import {AppService,person} from '../app.service'
@Component({
  selector: 'app-grid',
  templateUrl: './grid.component.html',
  styleUrl: './grid.component.css'
})
export class GridComponent {
  persons: person[] = [];
  people:any[]=[];
  selectedPerson:any=null;
  
  newPerson: person = { name: '', age: 0 };
  constructor(private AppService: AppService) {
    this.loadPersons();
  }
  loadPersons(): void {

    this.AppService.getPersons().subscribe(persons => this.persons = persons);
  }
  editPerson(person:any):void{
    this.selectedPerson={...person}
  }
  deletePerson(id:any):void{
    this.AppService.deletePerson(id).subscribe(() => {
      this.AppService.getPersons();
    });
  }
  clearSelection(): void {
    this.selectedPerson = null;
  }
  handleUpdate(): void {
    this.AppService.getPersons();
    this.clearSelection();
  }
}
