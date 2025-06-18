import { Component, OnInit } from '@angular/core';
import { Router } from '@angular/router';
import { AuthService } from '../../services/auth.service';
import { debug } from 'console';
@Component({
  selector: 'app-login',
  templateUrl: './login.component.html',
  styleUrls: ['./login.component.scss']
})
export class LoginComponent implements OnInit {

  constructor(
    private router: Router,
    private auth: AuthService
  ) { }

  ngOnInit(): void {
    debugger
  }

  username = '';
  password = '';
  loading = false;


  onLogin() {
    // this.loading = true;
    // this.auth.login(this.username, this.password).subscribe(success => {
    //   this.loading = false;
    //   if (success) {
    //     this.router.navigate(['/']); // redirect to dashboard or home
    //   } else {
    //     alert('Invalid credentials');
    //   }
    // });
  }

}
