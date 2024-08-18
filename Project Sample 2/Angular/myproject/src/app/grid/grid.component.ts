import { Component, OnInit } from '@angular/core';
import {DataService} from "../data.service";
@Component({
  selector: 'app-grid',
  templateUrl: './grid.component.html',
  styleUrl: './grid.component.css'
})
export class GridComponent implements OnInit {
  datas:any[]=[]
  srno:number=0
  searchQuery: string = '';
  selectedCategory: string="";
  filterdata=[...this.datas]
  constructor(private data:DataService){}
  ngOnInit(): void {
    //Called after the constructor, initializing input properties, and the first call to ngOnChanges.
    //Add 'implements OnInit' to the class.
    this.data.getData().subscribe(response=>this.datas=response)
    this.getDataUI()
  }
  getDataUI():void{
    this.data.getData().subscribe(response=>this.filterdata=response)
    console.log(this.datas)
  }
  deleteData(id:number):void{
    this.data.deleteData(id).subscribe(response=>console.log("data deleted successfully of id : "+id))
  }
  filterItems() {
    console.log(this.selectedCategory)
    this.filterdata = this.datas.filter(item => {
      if (this.selectedCategory==="all") {
        return item.text_input.toLowerCase().includes(this.searchQuery.toLowerCase()) 
      }
      else if(this.selectedCategory==="true"){

        return (
          item.text_input.toLowerCase().includes(this.searchQuery.toLowerCase()) &&(item.bool_input===true)
          // &&
          // (item.bool_input == this.selectedCategory)
        );
      }
      else if(this.selectedCategory==="false")
      {
        return (
          item.text_input.toLowerCase().includes(this.searchQuery.toLowerCase()) &&(item.bool_input===false)
          // &&
          // (item.bool_input == this.selectedCategory)
        );
      }
    });
  
  }
  onSearchQueryChange() {
    this.filterItems();
    console.log(this.filterdata);
  }

  onCategoryChange() {
    this.filterItems();
    // console.log(this.filterItems);

  }
}
