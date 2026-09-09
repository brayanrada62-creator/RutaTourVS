import { ComponentFixture, TestBed } from '@angular/core/testing';
import { Conductores } from './conductores';

describe('Conductores', () => {
  let component: Conductores;
  let fixture: ComponentFixture<Conductores>;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [Conductores],
    }).compileComponents();

    fixture = TestBed.createComponent(Conductores);
    component = fixture.componentInstance;
    await fixture.whenStable();
  });

  it('should create', () => {
    expect(component).toBeTruthy();
  });
});
