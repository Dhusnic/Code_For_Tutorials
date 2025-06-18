import { Component, OnInit } from '@angular/core';

@Component({
  selector: 'app-nav-bar',
  templateUrl: './nav-bar.component.html',
  styleUrls: ['./nav-bar.component.scss']
})
export class NavBarComponent implements OnInit {

  constructor() { }

  ngOnInit(): void {
    const savedTheme = localStorage.getItem('theme') as 'light' | 'dark';
    if (savedTheme) {
      this.theme = savedTheme;
      document.body.className = savedTheme + '-theme';
    }
  }
  navLinks = [
    { label: 'Home', path: '' },
    { label: 'Upload Prescription', path: 'upload' },
    { label: 'Schedule', path: 'schedule' },
    { label: 'About', path: 'about' },
    { label: 'Contact', path: 'contact' }
  ];

  isLoggedIn = true; // toggle this to false for testing guest view
  userName = 'JohnDoe'; // example username
  logout() {
    console.log('User logged out');
    this.isLoggedIn = false;
  }

  theme: 'light' | 'dark' = 'dark';


  toggleTheme() {
    this.theme = this.theme === 'dark' ? 'light' : 'dark';
    document.body.className = this.theme + '-theme';
    localStorage.setItem('theme', this.theme);
  }

}
