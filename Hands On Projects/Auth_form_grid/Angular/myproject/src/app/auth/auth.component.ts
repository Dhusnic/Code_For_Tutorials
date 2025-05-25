import { Component,EventEmitter,Output } from '@angular/core';
import { FormBuilder,Validator,FormGroup, Validators } from '@angular/forms';
import { Route,Router } from '@angular/router';
@Component({
  selector: 'app-auth',
  templateUrl: './auth.component.html',
  styleUrls: ['./auth.component.css']
})
export class AuthComponent {
  myForm:FormGroup;
  @Output() formSubmitted=new EventEmitter<any>();
  constructor(private router:Router,private fb:FormBuilder){
    this.myForm=this.fb.group({
      user_name:['',Validators.required],
      password:['',Validators.required]
    })
  }
  NavigateToSignUp()
  {
    this.router.navigate(['/sign_up']);
  }
  onSubmit()
  {
    if(this.myForm.valid)
    {
      this.formSubmitted.emit(this.myForm.value)
    }
  }
}
