import { ComponentFixture, TestBed } from '@angular/core/testing';

import { CsvFormComponent } from './csv-form.component';

describe('CsvFormComponent', () => {
  let component: CsvFormComponent;
  let fixture: ComponentFixture<CsvFormComponent>;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      declarations: [CsvFormComponent]
    })
    .compileComponents();
    
    fixture = TestBed.createComponent(CsvFormComponent);
    component = fixture.componentInstance;
    fixture.detectChanges();
  });

  it('should create', () => {
    expect(component).toBeTruthy();
  });
});
