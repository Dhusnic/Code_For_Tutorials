import { Component,EventEmitter, Output} from '@angular/core';
import { FormBuilder,FormControl,FormGroup,Validator, Validators } from '@angular/forms';
import { ApiService } from '../api.service';
@Component({
  selector: 'app-sign-up',
  templateUrl: './sign-up.component.html',
  styleUrls: ['./sign-up.component.css']
})
export class SignUpComponent {
  myForm:FormGroup
  @Output() formSubmmited=new EventEmitter<any>();
  constructor(private fb:FormBuilder,private api:ApiService){
    this.myForm=this.fb.group({
      user_name:["",Validators.required],
      password:["",Validators.required],
      Email:["",Validators.required],
      PhoneNumber:["",Validators.required]

    })
  }
  // this.myForm=new FormGroup({
  //   user_name:new FormControl()
  // })
  onSubmit()
  {
    if(this.myForm.valid)
    {
      this.formSubmmited.emit(this.myForm.value);
      this.api.sign_up(this.myForm.value).subscribe(
        Response=>{console.log('API response: ',Response)},
        error=>{console.error('Api Error:',error)}
      )
    }
    console.log(this.myForm.value);
  }
}
