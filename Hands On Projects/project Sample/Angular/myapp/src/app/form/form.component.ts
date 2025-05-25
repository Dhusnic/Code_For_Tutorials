import { Component, EventEmitter, Input, Output } from '@angular/core';
import { person, AppService } from '../app.service';
@Component({
  selector: 'app-form',
  templateUrl: './form.component.html',
  styleUrl: './form.component.css'
})
export class FormComponent {
  persons: person[] = [];
  @Input() newPerson: person = { name: '', age: 0 };
  @Output()  update=new EventEmitter<void>();
  @Output() cancel=new EventEmitter<void>();
  constructor(private AppService: AppService) {
  }  
  addPerson(): void {
    // this.AppService.addperson(this.newPerson).subscribe(person => {
    //   this.persons.push(person);
    //   this.newPerson = { name: '', age: 0 };
    // });
    if (this.newPerson.id) {
      this.AppService.editperson(this.newPerson).subscribe(() => {
        this.update.emit();
      });
    } else {
      this.AppService.addperson(this.newPerson).subscribe(() => {
        this.update.emit();
      });
    }
  }
  cancelEdit(): void {
    this.cancel.emit();
  }
}
