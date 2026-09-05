import { ComponentFixture, TestBed } from '@angular/core/testing';

import { PanelAdministrativo } from './panel-administrativo';

describe('PanelAdministrativo', () => {
  let component: PanelAdministrativo;
  let fixture: ComponentFixture<PanelAdministrativo>;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [PanelAdministrativo]
    })
    .compileComponents();

    fixture = TestBed.createComponent(PanelAdministrativo);
    component = fixture.componentInstance;
    await fixture.whenStable();
  });

  it('should create', () => {
    expect(component).toBeTruthy();
  });
});
