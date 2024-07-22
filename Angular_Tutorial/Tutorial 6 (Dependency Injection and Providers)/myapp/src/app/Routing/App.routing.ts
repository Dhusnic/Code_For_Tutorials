import { HomeComp } from "../Home/Home.component";
export const MainRoutes=[
    {path:'',component:HomeComp},
    {path:'Contact',loadChildren:()=>import('../Contact/Contact.module').then(m=>m.ContactModule)},
    {path:'Supplier',loadChildren:()=>import('../Supplier/Supplier.module').then(m=>m.SupplierModule)},
    {path:'Home',component:HomeComp}
];
