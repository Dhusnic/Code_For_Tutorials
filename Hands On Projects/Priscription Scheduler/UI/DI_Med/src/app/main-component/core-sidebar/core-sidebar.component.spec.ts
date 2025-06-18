import { ComponentFixture, TestBed } from '@angular/core/testing';

import { CoreSidebarComponent } from './core-sidebar.component';

describe('CoreSidebarComponent', () => {
  let component: CoreSidebarComponent;
  let fixture: ComponentFixture<CoreSidebarComponent>;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      declarations: [ CoreSidebarComponent ]
    })
    .compileComponents();

    fixture = TestBed.createComponent(CoreSidebarComponent);
    component = fixture.componentInstance;
    fixture.detectChanges();
  });

  it('should create', () => {
    expect(component).toBeTruthy();
  });
});
