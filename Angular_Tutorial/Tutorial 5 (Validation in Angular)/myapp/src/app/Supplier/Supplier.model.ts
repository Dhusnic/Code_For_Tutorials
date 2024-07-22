import {NgForm,FormGroup,Validators,FormBuilder, FormControl} from "@angular/forms";
export class Supplier {
    CustomerCode:string="";
    CustomerName:string="";
    CustomerAmount:number=0;
    formCustomerGroup:FormGroup;
    formCustomerDeleteGroup:FormGroup;
    constructor()
    {
        var _builder=new FormBuilder();
        this.formCustomerGroup=_builder.group({});//use the builder to create
        this.formCustomerDeleteGroup=_builder.group({});
        //contole->validations
        this.formCustomerGroup.addControl("CustomerNameControle",
            new FormControl('',Validators.required));
        //Coustmer Code Controle
        var validationsCollection=[Validators.required,Validators.pattern("^[0-9]{4,8}$")];
        // validationsCollection.push(Validators.required);
        // validationsCollection.push(Validators.pattern("^[0-9]{4,4}$"))
        this.formCustomerGroup.addControl("CustomerCodeControle",
            new FormControl('',Validators.compose(validationsCollection)))
        //Coustomer Amount Controle
        this.formCustomerGroup.addControl("CustomerAmountControle",new FormControl('',Validators.pattern("^[0-9]{1,5}$")))
        this.formCustomerDeleteGroup.addControl("CustomerDelete",new FormControl(''))
    }

}