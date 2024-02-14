import { HttpClient } from '@angular/common/http';
import { Injectable, signal } from '@angular/core';
import { ReplaySubject } from 'rxjs';

export type MuniMapping = {
  muni: string;
  name: string;
};

@Injectable({
  providedIn: 'root',
})
export class DataService {

  configuration = signal<any>({});
  settlements = signal<MuniMapping[]>([]);
  munis = signal<any>({});
  distances = signal<any>({});
  ready = new ReplaySubject<boolean>(1);
  required = 4;

  constructor(private http: HttpClient) {
    this.http.get('assets/configuration.json').subscribe(data => {
      this.configuration.set(data);
      this.checkReady();
    });
    this.http.get('assets/settlements.json').subscribe(data => {
      this.settlements.set(data as MuniMapping[]);
      this.checkReady();
    });
    this.http.get('assets/cities.json').subscribe(data => {
      this.munis.set(data as any);
      this.checkReady();
    });
    this.http.get('assets/distances.json').subscribe(data => {
      this.distances.set(data as any);
      this.checkReady();
    });
  }

  checkReady() {
    this.required--;
    if (this.required === 0) {
      this.ready.next(true);
      this.ready.complete();
    }
  }
}
