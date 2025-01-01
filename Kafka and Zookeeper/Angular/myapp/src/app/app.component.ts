import { Component, OnInit } from '@angular/core';
import { HttpClient } from '@angular/common/http';
@Component({
  selector: 'app-root',
  templateUrl: './app.component.html',
  styleUrl: './app.component.scss'
})
export class AppComponent implements OnInit{
  title = 'myapp';
  inputText: string = '';
  messages: string[] = [];

  constructor(private http: HttpClient) {}

  ngOnInit(): void {
    // Load existing data from MongoDB
    this.loadMessages();
  }

  onSubmit() {
    if (this.inputText) {
      // Send text to Django API
      this.http.post('http://localhost:8000/api/submit-text/', { text: this.inputText })
        .subscribe(response => {
          console.log('Text submitted successfully');
          this.loadMessages(); // reload messages after submission
        }, error => {
          console.error('Error submitting text', error);
        });

      this.inputText = ''; // Clear the input after submission
    }
  }

  loadMessages() {
    // Fetch all text data from MongoDB
    this.http.get<string[]>('http://localhost:8000/api/get-texts/')
      .subscribe(data => {
        this.messages = data;
      });
  }
}
