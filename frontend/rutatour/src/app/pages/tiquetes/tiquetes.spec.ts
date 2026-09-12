import { ComponentFixture, TestBed } from '@angular/core/testing';
import { Tiquetes } from './tiquetes';

describe('Tiquetes', () => {
  let component: Tiquetes;
  let fixture: ComponentFixture<Tiquetes>;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [Tiquetes],
    }).compileComponents();

    fixture = TestBed.createComponent(Tiquetes);
    component = fixture.componentInstance;
    await fixture.whenStable();
  });

  it('should create', () => {
    expect(component).toBeTruthy();
  });
});
