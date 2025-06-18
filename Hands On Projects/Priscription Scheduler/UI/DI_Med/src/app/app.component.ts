import { Component, OnInit } from '@angular/core';
import { Router } from '@angular/router';

@Component({
  selector: 'app-root',
  templateUrl: './app.component.html'
})
export class AppComponent implements OnInit {
  currentTheme: string = 'light-theme';

  constructor(public router: Router) {}

  ngOnInit(): void {
    // Check saved theme on load
    const savedTheme = localStorage.getItem('theme');
    if (savedTheme) {
      this.currentTheme = savedTheme;
    }

    // Optional: Listen to theme changes from a shared service if needed
  }

  // You can optionally add a method to toggle the theme globally here
  toggleTheme(): void {
    this.currentTheme = this.currentTheme === 'light-theme' ? 'dark-theme' : 'light-theme';
    localStorage.setItem('theme', this.currentTheme);
  }
}
