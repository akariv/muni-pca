import { Component, ElementRef, computed, effect, signal } from '@angular/core';
import { DataService, MuniMapping } from '../data.service';

import { MatAutocompleteModule, MatAutocompleteSelectedEvent } from '@angular/material/autocomplete';
import { MatFormFieldModule } from '@angular/material/form-field';
import { MatIconModule } from '@angular/material/icon';
import { FormControl, FormsModule, ReactiveFormsModule } from '@angular/forms';
import { MatInputModule } from '@angular/material/input';
import { AsyncPipe, CommonModule } from '@angular/common';
import { Observable, map, startWith, timer } from 'rxjs';
import { BidiModule } from '@angular/cdk/bidi';

@Component({
  selector: 'app-main-page',
  standalone: true,
  imports: [
    CommonModule,
    FormsModule,
    MatFormFieldModule,
    MatInputModule,
    MatAutocompleteModule,
    MatIconModule,
    ReactiveFormsModule,
    BidiModule,
    AsyncPipe,    
  ],
  templateUrl: './main-page.component.html',
  styleUrl: './main-page.component.less'
})
export class MainPageComponent {
  
  HEADER_STATUS = 'כללי - מעמד מוניציפלי';
  HEADER_DISTRICT = 'כללי - מחוז';
  HEADER_SOCIO_ECONOMIC = 'מדד חברתי-כלכלי - אשכול (מ-1 עד 10, 1 הנמוך ביותר)';
  HEADER_CITY_COUNT = 'יישובים במועצות אזוריות - סה"כ יישובים במועצה';

  HEADER_BUSINESS_RESIDENTIAL_INCOME = 'הכנסות בתקציב הרגיל - ארנונה למגורים (גבייה) (אלפי ש"ח)';
  HEADER_BUSINESS_COMMERCIAL_INCOME = 'הכנסות בתקציב הרגיל - ארנונה לא למגורים (גבייה) (אלפי ש"ח)';
  HEADER_BUSINESS_TOTAL_AREA = 'הכנסות בתקציב הרגיל - חיוב ארנונה סך הכל (שטח באלפי מ"ר)';
  HEADER_BUSINESS_RESIDENTIAL_AREA = 'הכנסות בתקציב הרגיל - חיוב ארנונה למגורים (שטח באלפי מ"ר)';

  HEADER_EXPENSE_EDUCATION = 'הוצאה לנפש על חינוך';
  HEADER_EXPENSE_WELFARE = 'הוצאה לנפש על רווחה';
  HEADER_EXPENSE_CULTURE = 'הוצאה לנפש על תרבות';

  muniSelection = new FormControl('');
  filteredOptions: Observable<string[]>;

  cityName = signal<string | null>(null);
  muniName = signal<string | null>(null);
  muni = computed(() => this.data.munis()[this.muniName() || ''] || null);
  norm = computed(() => this.data.configuration().columns);

  muniType = computed(() => this.muni().orig[this.HEADER_STATUS]);
  muniDistrict = computed(() => {
    const district = this.muni().orig[this.HEADER_DISTRICT]
    return district.indexOf('שומרון') >= 0 ? district : 'מחוז ' + district;
  });
  muniSociEconomic = computed(() => this.muni().orig[this.HEADER_SOCIO_ECONOMIC]);
  muniExpense = computed(() => this.muni().norm.EXPENSE / 1000);
  muniArea = computed(() => this.muni().norm.AREA);
  muniPop = computed(() => this.muni().norm.POP * 1000);
  muniNumCities = computed(() => this.muni().orig[this.HEADER_CITY_COUNT]);

  muniEducation = computed(() => (this.muni().values[this.HEADER_EXPENSE_EDUCATION] / this.muni().norm.POP));
  muniWelfare = computed(() => (this.muni().values[this.HEADER_EXPENSE_WELFARE] / this.muni().norm.POP));
  muniCulture = computed(() => (this.muni().values[this.HEADER_EXPENSE_CULTURE] / this.muni().norm.POP));

  muniBusinessIncome = computed(() => 100 * this.muni().orig[this.HEADER_BUSINESS_COMMERCIAL_INCOME] / (this.muni().orig[this.HEADER_BUSINESS_RESIDENTIAL_INCOME] + this.muni().orig[this.HEADER_BUSINESS_COMMERCIAL_INCOME]));
  muniBusinessArea = computed(() => 100 - 100 * this.muni().orig[this.HEADER_BUSINESS_RESIDENTIAL_AREA] / this.muni().orig[this.HEADER_BUSINESS_TOTAL_AREA]);


  muniEducationMedal = computed(() => this.medal(this.muniEducation(), this.distancesEducation().map((m: any) => m.education)));
  muniWelfareMedal = computed(() => this.medal(this.muniWelfare(), this.distancesWelfare().map((m: any) => m.welfare)));
  muniCultureMedal = computed(() => this.medal(this.muniCulture(), this.distancesCulture().map((m: any) => m.culture)));
  muniBusinessMedal = computed(() => this.medal(this.muniBusinessIncome(), this.distancesBusiness().map((m: any) => m.businessIncome)));

  reveal = signal(0);
  canAdvance = signal(true);

  distances = computed(() => {
    const distances = this.data.distances()[this.muniName() || ''] || [];
    return distances.slice(0, 5).map((distance: any) => {
      const muni = this.data.munis()[distance[0]] || {};
      muni.name = distance[0];
      muni.diff_text = distance[1].map((col: string) => {
        const norm = this.norm()[col].norm;
        let annotations = this.norm()[col].annotations?.[0] || '';
        console.log('annotations:', annotations);
        if (annotations === '1') {
          annotations = `<span title='יחסית לגודל האוכלוסיה ברשות'>&sup1;</span>`;
        } else if (annotations === '2') {
          annotations = `<span title='יחסית לתקציב השנתי של הרשות'>&sup2;</span>`;
        } else if (annotations === '3') {
          annotations = `<span title='יחסית לשטח השיפוט של הרשות'>&sup3;</span>`;
        }
        const mine = this.muni().values[col] / (norm ? this.muni().norm[norm] : 1);
        const theirs = muni.values[col] / (norm ? muni.norm[norm] : 1);
        console.log('mine:', mine, 'theirs:', theirs);
        const options = {maximumFractionDigits: 1, minimumFractionDigits: 0};
        if (!!theirs && !!mine) {
          if (theirs > 2*mine) {
            return `פי ${(theirs/mine).toLocaleString('he-IL', options)} יותר ${col}${annotations}`;
          } else if (mine > 2*theirs) {
            return `פי ${(mine/theirs).toLocaleString('he-IL', options)} פחות ${col}${annotations}`;
          } else if (mine > theirs) {
            return `כ-${(100 - 100*theirs/mine).toFixed(0)}% פחות ${col}${annotations}`;
          } else if (theirs > mine) {
            return `כ-${(100*theirs/mine - 100).toFixed(0)}% יותר ${col}${annotations}`;
          }
        }
        return null;
      }).slice(0, 2).filter((x: any) => !!x).join(' ו');
      muni.education = (muni.values[this.HEADER_EXPENSE_EDUCATION] / this.muni().norm.POP);
      muni.welfare = (muni.values[this.HEADER_EXPENSE_WELFARE] / this.muni().norm.POP);
      muni.culture = (muni.values[this.HEADER_EXPENSE_CULTURE] / this.muni().norm.POP);
      muni.businessIncome = 100 * muni.orig[this.HEADER_BUSINESS_COMMERCIAL_INCOME] / (muni.orig[this.HEADER_BUSINESS_RESIDENTIAL_INCOME] + muni.orig[this.HEADER_BUSINESS_COMMERCIAL_INCOME]);
      muni.businessArea = 100 - 100 * muni.orig[this.HEADER_BUSINESS_RESIDENTIAL_AREA] / muni.orig[this.HEADER_BUSINESS_TOTAL_AREA];
      return muni;
    });
  });
  distancesEducation = computed(() => this.distances().slice().sort((a: any, b: any) => b.education - a.education));
  distancesWelfare = computed(() => this.distances().slice().sort((a: any, b: any) => b.welfare - a.welfare));
  distancesCulture = computed(() => this.distances().slice().sort((a: any, b: any) => b.culture - a.culture));
  distancesBusiness = computed(() => this.distances().slice().sort((a: any, b: any) => b.businessIncome - a.businessIncome));
  
  constructor(public data: DataService, private el: ElementRef) {
    effect(() => {
      console.log('muni:', this.muni());
      if (!this.muniName() && this.data.settlements().length) {
        this.selectCity('רעננה');
      }
    }, {allowSignalWrites: true});
  }
  
  ngOnInit() {
    this.filteredOptions = this.muniSelection.valueChanges.pipe(
      startWith(''),
      map(value => this._filter(value || '')),
    );
  }

  getMuni(name: string) {
    return this.data.munis()[this.data.settlements().find(option => option.name === name)?.muni || ''] || {};
  }

  private _filter(value: string): string[] {
    const filterValue = value.toLowerCase();
    return this.data.settlements().filter(option => option.name.includes(filterValue)).map(option => option.name);
  }

  selected(event: MatAutocompleteSelectedEvent) {
    const value = event.option.value;
    this.selectCity(value);
    this.reveal.set(1);
    this.advance();
  }
  
  selectCity(value: string) {
    this.cityName.set(value);
    this.muniName.set(this.data.settlements().find(option => option.name === value)?.muni || null);
  }
  
  medal(value: number, values: number[]) {
    if (value > values[0]) {
      return 'workspace_premium';
    } else if (value > values[1]) {
      return 'sentiment_very_satisfied';
    } else if (value > values[2]) {
      return 'sentiment_satisfied';
    } else if (value > values[3]) {
      return 'sentiment_neutral';
    }
    return 'sentiment_dissatisfied';
  }

  advance() {
    this.canAdvance.set(false);
    this.reveal.set(this.reveal() + 1);
    timer(0).subscribe(() => {
      const sections = this.el.nativeElement.querySelectorAll('section');
      const lastSection: HTMLElement = sections[sections.length - 1];
      lastSection.scrollIntoView({behavior: 'smooth', block: 'start'});
    });
    timer(1000).subscribe(() => this.canAdvance.set(this.reveal() !== 1 && this.reveal() !== 14));
  }
}
